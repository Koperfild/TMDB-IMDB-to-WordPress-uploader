# Scrape TMDB to WP

## Dependencies
```
pip3 install -r requirements.txt
```

## Usage
### Movies
By default, there is setted movies in `movies.txt` and storage url is `https://megavideo.site/storage/movies/`, so you can just run like this:

```
python3.6 fetch_movies.py
```

Or, if you need to change storage or input file:

```
python3.6 fetch_movies.py -u storage_url -f filename.txt
```

Or, you can use just url option:

```
python3.6 fetch_movies.py -j storage_url
```

To display help menu run:
```
$  python3.6 fetch_movies.py --help
usage: fetch_movies.py [-h] -d DOMAIN -U USERNAME -p PASSWORD [-u URL]
                       [-f FILE] [-j JUST_URL] [-l LIMIT]

Fetch data from TMDB and post it on WordPress website

optional arguments:
  -h, --help            show this help message and exit
  -d DOMAIN, --domain DOMAIN
                        Specify WP domain url.
  -U USERNAME, --username USERNAME
                        Specify WP username.
  -p PASSWORD, --password PASSWORD
                        Specify WP username.
  -u URL, --url URL     Storage url to scrape filenames
  -f FILE, --file FILE  File with movies
  -j JUST_URL, --just_url JUST_URL
                        Just url flag
  -l LIMIT, --limit LIMIT
                        Set limit for all fields
```

### TV Shows
By default, there is setted movies in `tv_episodes.txt` and storage url is `http://disaster.blog4sports.xyz/baf/`, so you can just run like this:

```
python3.6 fetch_tv.py
```

Or, if you need to change storage or input file:

```
python3.6 fetch_tv.py -u storage_url -f filename.txt
```

Or, you can use just url option:

```
python3.6 fetch_tv.py -j storage_url
```

To display help menu run:
```
$  python3.6 fetch_tv.py --help
usage: fetch_tv.py [-h] -d DOMAIN -U USERNAME -p PASSWORD [-u URL] [-f FILE]
                   [-j JUST_URL] [-l LIMIT]

Fetch data from TMDB and post it on WordPress website

optional arguments:
  -h, --help            show this help message and exit
  -d DOMAIN, --domain DOMAIN
                        Specify WP domain url.
  -U USERNAME, --username USERNAME
                        Specify WP username.
  -p PASSWORD, --password PASSWORD
                        Specify WP username.
  -u URL, --url URL     Storage url to scrape filenames
  -f FILE, --file FILE  File with tv episodes
  -j JUST_URL, --just_url JUST_URL
                        Just url flag
  -l LIMIT, --limit LIMIT
                        Set limit for all fields
```
