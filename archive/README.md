## Word! Automating a Hip-hop word of the day blog
### PyCon Canada 2016, November 13th 2016

### Abstract 
Have you ever been surprised by sophisticated vocabulary used by some hip-hop artists? With standard data science tools, I search a large corpus of hip-hop lyrics in order to extract rhyming couplets that include uncommon and interesting words. Using curated output from this code, I demonstrate how to automate the creation of short text-based posts for a hip-hop themed "Word of the Day" blog.

### Details
In this notebook, I go from raw text files of rap lyrics scraped (using curl) from ohhla.com and try to extract rare and interesting words in order to prepare data for the website RapWords (http://rapwords.tumblr.com/). Specifically, I choose a rhyme by "Nas" in the song "Memory Lane" that includes the word trifle, which I process with a series of functions in order to produce HTML for a blog post. Humorously, the script detects that "trifle" is a noun based on the limited information in the sentence, rather than a verb, hence the final image in the document (what Nas might've actually meant!).

### Dependencies
This notebook was written with Python 3.5 with Jupyter 1.0.0. There are several additional libraries used in this talk,
* standard library (re, glob, collections, html)
* pandas (http://pandas.pydata.org/), numpy
* wiktionaryparser (https://github.com/Suyash458/WiktionaryParser), for dictionary definitions
* spotipy (https://github.com/plamere/spotipy) / Google Data API (https://github.com/google/google-api-python-client) (optional, for getting YouTube links)
* nltk (https://github.com/nltk/nltk), for parts of speech tagging
* pypronouncing (https://github.com/aparrish/pronouncingpy), for word pronounciations
* pytumblr (Python3 fork) (https://github.com/jabbalaci/pytumblr) / oauthlib / oauthlib_requests (optional, for posting online)
