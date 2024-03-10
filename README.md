# Information-Retreival-Project

Our final project for the "Information Gathering" course at Ben-Gurion University involves the development of a search engine adapted to Wikipedia in English. Capable of searching over 6 million Wikipedia documents, this search engine is designed to quickly and efficiently return relevant results in response to queries from users across the entire collection of Wikipedia articles. We have carefully refined and implemented these methodologies to provide an optimal search experience for our users.

### Files Included
1. `search_frontend.py` - contains the 6 methods required to implement the search functionality: search, search according to document title, search according to document body, search according to document anchor text, get page views and get page rank functions. We currently only implement the search function
2. `backend_engine.py` - contains the query extension, query tokenization methods and contain all the ranking methods for the results retrieval
3. `inverted_index_gcp.py` - contains the inverted index file and all its methods.
4. create indexs file - The establishment of the various indexes in GCP.
5. create dicts file - The establishment of the various dictionaries in GCP for the purpose of quick retrieval of data.
6. `indexs_files.txt` - contains the files list from the buckets as required.

### How to use
The search engine can be used by running the `search_frontend.py` file.

### Retrival Methodes:
Our search engine utilizes a combination of various retrieval methods:

* Inverted Index
* TF-IDF
* BM-25
* Word2vac
* Page Rank
* Page view

### Indexes:
* Index_Title
* Index_Body


### Notes:
A link to our project on Google Cloud Storage - 

The external IP address of a VM: http://34.41.43.34:8080 you can access our search engine by activating it at /search?query=YOUR_QUERY. Contact us via email for access to the virtual machine (:

Nicole Kaplan - nicoleka@post.bgu.ac.il , Ayelet Hashahar Cohen - ayelethc@post.bgu.ac.il, tzuf Lahan - lahantz1234@post.bgu.ac.il 
