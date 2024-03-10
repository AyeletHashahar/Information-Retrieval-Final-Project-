# -*- coding: utf-8 -*-
"""search_backend.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1DzA8K5vj5j3aCBrz1P2fgFfeEqBlMC6s

Imports
"""

import concurrent
import sys
from collections import Counter, OrderedDict, defaultdict
import itertools
from itertools import islice, count, groupby
#import google
import pandas as pd
import os
import re
from operator import itemgetter
import nltk
from nltk.stem.porter import *
from nltk.corpus import stopwords
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from time import time
from timeit import timeit
from pathlib import Path
import numpy as np
import itertools
import math
from inverted_index_text_gcp import *
from inverted_index_title_gcp import *
from contextlib import closing
import gensim.models
import gensim.downloader
import gc
from google.cloud import storage
import pickle
import pyspark
nltk.download('stopwords')

"""Initializing infrastructure"""

bucket_name = 'bucket-ir-project-nicoleayelet'
title_path = 'title_index/postings_gcp_title_index/'
text_path = 'text_index/postings_gcp_text_index/'

def read_pickle(bucket_name, pickle_route):
    client = storage.Client()
    blob = client.bucket(bucket_name).blob(pickle_route)
    pick = pickle.loads(blob.download_as_string())
    return pick


inverted_title = read_pickle(bucket_name, "title_index/postings_title_gcp/title_index.pkl")
inverted_text = read_pickle(bucket_name, "text_index/postings_text_gcp/text_index.pkl")
pagerank_dict = read_pickle(bucket_name, "page_rank/pagerank_dict.pkl")
pageview_dict = read_pickle(bucket_name, "PageView/PageView.pkl")
id_title_dict = read_pickle(bucket_name, "title_id_dict/dict_doc_id_and_title.pkl")


### We conducted a thorough exploration of an Word2Vec implementation
### and determined that it does not align well with our engine
###############################################################################################

# glove_vectors = gensim.downloader.load("glove-wiki-gigaword-300")

# def similar_one_word(token, word2vec_model):
#     candidates = word2vec_model.most_similar(positive=token, topn=3)
#     res = [word for word, similarity in candidates if similarity > 0.7]
#     for tok in res:
#         token += tokenize(tok)
#     return token[:5]
#
#
# def similar_words(list_of_tokens, word2vec_model):
#     sim_words = []
#     res = []
#
#     for token in list_of_tokens:
#         candidates = word2vec_model.most_similar(positive=token, topn=1)
#         res += [(similarity, word) for word, similarity in candidates if similarity > 0.7]
#
#     sim_words += list_of_tokens
#     for sim, tok in sorted(res, reverse=True):
#         if len(sim_words) < 5:
#             sim_words += tokenize(tok)
#         else:
#             break
#
#     return sim_words

###############################################################################################


# words to tokens
english_stopwords = frozenset(stopwords.words('english'))
corpus_stopwords = ["category", "references", "also", "external", "links",
                    "may", "first", "see", "history", "people", "one", "two",
                    "part", "thumb", "including", "second", "following",
                    "many", "however", "would", "became"]

all_stopwords = english_stopwords.union(corpus_stopwords)
RE_WORD = re.compile(r"""[\#\@\w](['\-]?\w){2,24}""", re.UNICODE)


def tokenize(text):
  tokens = [token.group() for token in RE_WORD.finditer(text.lower()) if token.group() not in all_stopwords]
  return tokens


def title_for_id(doc_id):
  id_title = id_title_dict.get(doc_id, 0)
  if id_title:
    return id_title
  else:
    return "no matching title"


def read_posting_list(inverted, w, file_path) -> object:
    TUPLE_SIZE = 6
    with closing(MultiFileReader()) as reader:
        locs = inverted.posting_locs[w]
        posting_list = []
        try:
          b = reader.read(locs, inverted.df[w] * TUPLE_SIZE, file_path)
          for i in range(inverted.df[w]):
              doc_id = int.from_bytes(b[i * TUPLE_SIZE:i * TUPLE_SIZE + 4], 'big')
              tf = int.from_bytes(b[i * TUPLE_SIZE + 4:(i + 1) * TUPLE_SIZE], 'big')
              posting_list.append((doc_id, tf))

        except:
            print('couldnt use reader')
            return None

        return posting_list



class BM25:

    def __init__(self, index, file_path, k1=1.5, b=0.75):
        self.b = b
        self.k1 = k1
        self.index = index
        self.N = len(index.DL)
        self.AVGDL = sum(index.DL.values()) / self.N
        self.file_path = file_path
        self.idf = {}


    def calc_idf(self, tokens_list):
        return {token: math.log(1 + (self.N - self.index.df.get(token, 0) + 0.5) / (self.index.df.get(token, 0) + 0.5))
                for token in tokens_list if token in self.index.df}


    def get_doc_score(self, query, doc_id, posting_list_dict):
        doc_score = 0.0
        doc_len = self.index.DL.get(doc_id, 0)
        for term in query:
            if term in self.index.df and doc_id in posting_list_dict.get(term, {}):
                freq = posting_list_dict[term][doc_id]
                numerator = self.idf[term] * freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self.AVGDL)
                doc_score += numerator / denominator
        return doc_score


    def get_doc_score_unique(self, query, doc_id, posting_list_dict):
        score = 0.0
        doc_len = self.index.DL.get(doc_id, 0)
        for term in set(query):
            if term in self.index.df and doc_id in posting_list_dict.get(term, {}):
                freq = posting_list_dict[term][doc_id]
                numerator = self.idf[term] * freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self.AVGDL)
                score += numerator / denominator
        return score


    def search_union_docs(self, query_tokenized, N=30):
        try:
            ## code regarding word2vec
            # query_words_count = len(query_tokenized)
            #
            # if query_words_count == 1:
            #   query_tokenized = similar_one_word(query_tokenized, glove_vectors)
            # else:
            #   query_tokenized = similar_words(query_tokenized, glove_vectors)

            self.idf = self.calc_idf(query_tokenized)

            d_posting_lists = {}
            candidates = []

            for term in np.unique(query_tokenized):
                if term in self.index.df:
                    try:
                        curr_lst = read_posting_list(self.index, term, self.file_path)
                        d_posting_lists[term] = dict(curr_lst)
                        candidates += curr_lst
                    except Exception as e:
                        print(f"An error occurred while reading posting list for term '{term}': {e}")
                        continue

            candidates = set(doc_id for doc_id, _ in candidates)

            bm_25_scores = [(doc_id, self.get_doc_score(query_tokenized, doc_id, d_posting_lists)) for doc_id in candidates]
            bm_25_scores.sort(key=lambda x: x[1], reverse=True)

            return bm_25_scores[:N]

        except Exception as e:
            print(f"No match for {query_tokenized}. Error: {e}")


    def search_intersection_docs(self, query_tokenized, N=30):
      try:
          ## code regarding word2vec
          # query_words_count = len(query_tokenized)
          #
          # if query_words_count == 1:
          #     query_tokenized = similar_one_word(query_tokenized, glove_vectors)
          # else:
          #     query_tokenized = similar_words(query_tokenized, glove_vectors)


          self.idf = self.calc_idf(query_tokenized)

          d_posting_lists = {}
          candidates = []

          for term in np.unique(query_tokenized):
              if term in self.index.df:
                  try:
                      curr_lst = read_posting_list(self.index, term, self.file_path)
                      d_posting_lists[term] = dict(curr_lst)
                      candidates.append([item[0] for item in curr_lst])
                  except Exception as e:
                      print(f"An error occurred while reading posting list for term '{term}': {e}")
                      continue

          common_doc_ids = set(candidates[0])
          for inner_list in candidates[1:]:
              common_doc_ids.intersection_update(inner_list)

          candidates = list(common_doc_ids)

          bm_25_scores = [(doc_id, self.get_doc_score(query_tokenized, doc_id, d_posting_lists)) for doc_id in candidates]
          bm_25_scores.sort(key=lambda x: x[1], reverse=True)

          return bm_25_scores[:N]

      except Exception as e:
          print(f"No match for {query_tokenized}. Error: {e}")



def title_text_score(titles_score_list, body_scores_list, title_weight, text_weight):

    temp_dict = defaultdict(float)

    for doc_id, score in titles_score_list:
        temp_dict[doc_id] += title_weight * score

    for doc_id, score in body_scores_list:
        temp_dict[doc_id] += text_weight * score

    return temp_dict


def title_text_score_with_pagerank_pageviews(doc_id_rank_dict, BM_weight, pagerank_weight, pageview_weight):

    for key, val in doc_id_rank_dict.items():
        BM_score = val
        page_rank_score = pagerank_dict.get(key, 0)
        page_view_score = pageview_dict.get(key, 0)
        doc_id_rank_dict[key] = (BM_score * BM_weight + pagerank_weight * pagerank_weight + page_view_score * pageview_weight)

    return doc_id_rank_dict


def search_helper(query):

    query_tokenized = tokenize(query)
    query_tokenized_len = len(query_tokenized)

    BM25_title = BM25(inverted_title, title_path)
    BM25_text = BM25(inverted_text, text_path)

    if query_tokenized_len == 1:
        title_score_one = BM25_title.search_intersection_docs(query_tokenized)
        text_score_one = BM25_text.search_union_docs(query_tokenized)
        total_score = title_text_score(title_score_one, text_score_one, 0.6, 0.4)
    else:
        title_score = BM25_title.search_intersection_docs(query_tokenized)
        text_score = BM25_text.search_intersection_docs(query_tokenized)
        total_score = title_text_score(title_score, text_score, 0.4, 0.6)

    total_score = title_text_score_with_pagerank_pageviews(total_score, 0.75, 0, 0.25)

    sort_scores = list(sorted(total_score.items(), key=lambda x: x[1], reverse=True)[:30])
    res = [(str(doc_id), title_for_id(doc_id)) for doc_id, score in sort_scores]

    return list(res)
