"""Tools to work with TMDB and IMDB APIs. Queries to these services. Also includes some optimizations to make these
queries in simultaneous manner"""

import logging
import traceback
import tmdbsimple as tmdb
from imdb import IMDb
import logging
from tv import TVEpisode
from requests.exceptions import HTTPError
import concurrent
from time import sleep
import requests
import json
import time
import threading
from movie import Movie
from wp import error_log
from loggers import error_log
from helpers import json_to_obj, read_tv_ids_from_file, read_movie_ids_from_file


IMDb_LOGGING_LEVEL = "ERROR"
MAX_TRIES = 25
#suppress logging in piculet
logging.getLogger("imdb.parser.http.piculet").addHandler(logging.NullHandler())
logging.getLogger('imdb.parser.http.piculet').propagate = False
log = logging.getLogger(__name__)
sem = threading.BoundedSemaphore(40)


def _request(self, method, path, params=None, payload=None):
    """Made to replace _request in tmdbsimple for situation when there are too much simultaneous requests and TMDB sets
    quantity limit for requests number per some period of time. It retries till success."""
    url = self._get_complete_url(path)
    params = self._get_params(params)
    with sem:
        is_processed = False
        while not is_processed:
            try:
                response = requests.request(
                    method, url, params=params,
                    data=json.dumps(payload) if payload else payload,
                    headers=self.headers)
                if response.status_code == 429 and response.reason == 'Too Many Requests':
                    retry_after = int(response.headers._store['retry-after'][1])
                    time.sleep(retry_after + 1)
                else:
                    is_processed = True
                    response.raise_for_status()
                    response.encoding = 'utf-8'
            except requests.exceptions.ConnectionError as e:
                raise e
            except Exception as e:
                raise e

    return response.json()

tmdb.base.TMDB._request = _request

class IMDBClient:
    """
    Class representation of IMDb API.
    """

    def __init__(self, loggingLevel='ERROR'):
        self.client = IMDb(loggingLevel=loggingLevel)

    def search_tv(self, title):
        """ 
        Search TV show by his title on IMDb

        :type title: str
        """
        return self.client.search_movie(title)

    def get_show_by_id(self, show_id):
        """ 
        Gets TV show by his id on IMDb

        :type show_id: int
        """
        return self.client.get_movie(show_id)

    def get_show_episodes(self, show_id):
        """ 
        Gets TV show _episodes by his id on IMDb

        :type show_id: int
        """
        return self.client.get_movie_episodes(show_id)

    def get_episode_id(self, episodes, season_num, episode_num):
        """ 
        Gets TV show episode id 
        Returns episode_id
        :type episodes: list
        :param episodes: list of TV show _episodes
        :type season_num: int
        :type episode_num: int
        rtype: int
        """
        episodes = episodes.get("data").get("episodes")
        season_episodes = episodes.get(season_num)
        # Sometimes _episodes number starts with 0, sometimes with 1
        if 0 in season_episodes.keys():
            episode_num -= 1

        episode = season_episodes.get(episode_num)
        try:
            episode_id = episode.movieID
        except AttributeError:
            log.info(vars(episode))
            traceback.format_exc()
            log.exception("Exception")
            log.info(f"Something wrong while getting episode id.")
            return 0

        return episode_id


class TMDBClient:
    """
    Class representation of IMDb API.
    """

    def __init__(self, api_key):
        tmdb.API_KEY = api_key
        self._discover = tmdb.Discover()

    def find_movie(self, movie_id):
        """
        Find movie by id

        type: movie_id: int 
        """
        return tmdb.Movies(movie_id)

    def search_movie_id(self, query, year=None):
        """
        Search movie by title and year on TMDb

        type: query: str 
        type: year: int 

        rtype: int
        """
        #delete j
        # log.info("before search_movie_id")
        #synchronize_TMDB()
        response = tmdb.Search().movie(query=query, year=year, adult=True, language="ru")
        results = response.get("results")
        movie_id = results[0].get("id") if results else 0
        return movie_id

    def search_tv_show_id(self, query, year=None):
        """
        Search tv_show by title and year on TMDb
        type: query: str
        type: year: int 
        rtype: int
        """
        #delete j
        #log.info(f"before search_tv_show_id: {query} {year}")
        #delete j
        #synchronize_TMDB()
        response = tmdb.Search().tv(query=query, year=year, adult=True)
        results = response.get("results")
        movie_id = results[0].get("id") if results else 0
        return movie_id

    def find_episode(self, tv_show_id, season, episode):
        """
        Finds episode of TV show by id, season and episode 
        type: tv_show_id: int
        type: season: int 
        type: episode: int 
        """
        return tmdb.TV_Episodes(
            tv_show_id, season_number=season, episode_number=episode
        )

    def find_tv(self, tv_show_id):
        '''
        Finds tv show by id
        :param tv_show_id:
        :return:
        '''
        return tmdb.TV(tv_show_id)

    def find_all_tv_episodes(self, tv_show_id, language=None):
        '''
        Finds all episodes for tv show with passed id
        :param tv_show_id:
        :param language:
        :return:
        '''
        tv = self.find_tv(tv_show_id)
        episodes = tv.videos(language=language) if language is not None else tv.videos()
        return episodes


def get_episode_infos(episodes, storage_url, limit, language):
    '''
    Gets info from TMDB and IMDB. Also makes translation (inside TVEpisode.__init__())
    :param episodes Episode
    :param storage_url: from args.url
    :param limit: from args.limit
    :param language: from args.language
    :return: [episod_info]
    '''
    with concurrent.futures.ThreadPoolExecutor() as executor:
        args = ((episode, storage_url, limit, language) for episode in episodes)
        res = []
        for episode, ep_info in zip(episodes, executor.map(lambda p: get_episode_info(*p), args)):
            if ep_info is None:
                error_log.error(f"error getting info for {episode._episode_line}")
                log.error(f"error getting info for {episode._episode_line}")
            else:
                res.append(ep_info)
        return res

def get_episode_info(episode, storage_url, limit, language):
    '''
    Gets info from TMDB and IMDB. Also makes translation (inside TVEpisode.__init__())
    :param episode Episode
    :param storage_url: from args.url
    :param limit: from args.limit
    :param language: from args.language
    :return:
    '''
    tmdb_client = TMDBClient(API_KEY)
    # First we need to find episode_id on TMDB by episode name
    episode_id = None
    tries = 0
    while episode_id is None:
        if tries > MAX_TRIES:
            raise Exception('Too much attempts')
        try:
            tries += 1
            episode_id = tmdb_client.search_tv_show_id(episode.episode_title)
            if not episode_id:
                log.info(f"There is no {episode.episode_title} {episode.season_num}, {episode.ep_num} on TMDB.")
                return None
        except HTTPError as e:
            if e.response.reason == 'Too Many Requests' and e.response.status_code == 429:
                log.info('Too many requests to TMDB. Waiting limit refreshment')
                sleep(float(e.response.headers._store['retry-after'][1]) + 0.1)
            else:
                log.info("Something wrong getting info from TMDB")
                return None
    # Scrape episode info from TMDB. id, season_num, ep_num
    tmdb_episode_object = tmdb_client.find_episode(episode_id, episode.season_num, episode.ep_num)
    log.info(f"TMDB info scraped:{str(episode)}")
    # Creating an instance of the Movie
    episode_info = None
    while episode_info is None:
        try:
            #get info and credits from tmdb
            response = tmdb_episode_object.info(language=language, append_to_response='credits')
            credits = response['credits']
            info = response
            episode_info = TVEpisode(
                episode.episode_title,
                info,
                credits,
                link=episode.link,
                storage_url=storage_url,
                limit=limit,
                language=language
            )
        except ValueError:
            log.info(f"Not enough info on TMDB for {episode.episode_title}. Skipping.")
            return None
        except HTTPError as e:
            if e.response.reason == 'Too Many Requests' and e.response.status_code == 429:
                log.info('Too many requests to TMDB. Waiting limit refreshment')
                sleep(float(e.response.headers._store['retry-after'][1])+ 0.1)
            else:
                log.info(f"Something wrong with connection")
                error_log.error(f"Something wrong with connection {episode.episode_title}. Skipping.")
                return None

    try:
        imdb_client = IMDBClient()
        episode_info.fetch_info_from_imdb(imdb_client)
    except Exception as e:
        log.info(f"Something wrong while fetching data from IMDb")
        error_log.error(f"{episode.episode_title}: {e}")
        episode_info = None
        # raise(e)
        # traceback.print_exc()
    if episode_info:
        return episode_info
    else: return None


def get_movie_infos(movies, storage_url, limit, language):
    '''
    Gets info from TMDB. Also makes translation (inside Movie.__init__())
    :param movies iterable WPMovie
    :param storage_url: from args.url
    :param limit: from args.limit
    :param language: from args.language
    :return: [episod_info]
    '''
    with concurrent.futures.ThreadPoolExecutor() as executor:
        args = ((movie, storage_url, limit, language) for movie in movies)
        return list(executor.map(lambda p: get_movie_info(*p), args))
    #delete replaced with executor
    # episode_infos = await asyncio.gather(*[get_episode_info(ep, storage_url, limit, language) for ep in episodes])


def get_movie_info(movie, storage_url, limit, language):
    '''
    Gets info from TMDB. Also makes translation (inside Movie.__init__())
    :param movie WPMovie
    :param storage_url: from args.url
    :param limit: from args.limit
    :param language: from args.language
    '''
    tmdb_client = TMDBClient(API_KEY)
    movie_id = None
    movie_info = None
    res = None
    tries = 0
    while movie_info is None:
        if tries > MAX_TRIES:
            break
        try:
            tries += 1
            movie_id = tmdb_client.search_movie_id(movie.title, movie.year)
            if not movie_id:
                log.info(
                    f"There is no {movie.title} {f'({movie.year})' if movie.year else ''} on TMDB.")
                log.info(f"Trying to find without year specified:{movie.title} {f'({movie.year})' if movie.year else ''}")
                movie_id = tmdb_client.search_movie_id(movie.title)
                if not movie_id:
                    log.info(f"{movie.title} {f'({movie.year})' if movie.year else ''} not found on TMDB. Skipping")
                    return None
            # Scrape movie info from TMDB
            movie_info = tmdb_client.find_movie(movie_id)
            log.info(f"Info scraped:{movie.title} {movie.year}")
            # Creating an instance of the Movie
            res = Movie(
                movie_info, storage_url, movie.title, link=movie.link, limit=limit, language=language
            )
        except HTTPError as e:
            if e.response.reason == 'Too Many Requests' and e.response.status_code == 429:
                log.info(f'Too many requests to TMDB. Waiting limit refreshment: {movie.title} {movie.year}')
                sleep(float(e.response.headers._store['retry-after'][1]) + 0.1)
            else:
                log.info(f"Something wrong getting info from TMDB:{movie.title} {movie.year}")
                return None
    if res:
        return res
    else:
        return None


def get_movie_infos_by_id(id_file_path, storage_url, limit, language):
    ids = read_movie_ids_from_file(id_file_path)
    return _get_movie_infos_by_id(ids, storage_url, limit, language)

def _get_movie_infos_by_id(ids, storage_url, limit, language):
    '''
    Gets info from TMDB. Also makes translation (inside Movie.__init__())
    :param storage_url: from args.url
    :param limit: from args.limit
    :param language: from args.language
    :return: [episod_info]
    '''
    with concurrent.futures.ThreadPoolExecutor() as executor:
        args = ((id, storage_url, limit, language) for id in ids)
        return list(executor.map(lambda p: get_movie_info_by_id(*p), args))
    #delete replaced with executor
    # episode_infos = await asyncio.gather(*[get_episode_info(ep, storage_url, limit, language) for ep in episodes])


def get_movie_info_by_id(id, storage_url, limit, language):
    '''
    Gets info from TMDB. Also makes translation (inside Movie.__init__())
    :param id WPMovie
    :param storage_url: from args.url
    :param limit: from args.limit
    :param language: from args.language
    '''
    tmdb_client = TMDBClient(API_KEY)
    movie_info = None
    res = None
    tries = 0
    while movie_info is None:
        if tries > MAX_TRIES:
            break
        try:
            tries += 1
            # Scrape movie info from TMDB
            movie_info = tmdb_client.find_movie(id)

            # Creating an instance of the Movie
            res = Movie(
                movie_info, storage_url, movie_name=None, link=None, limit=limit, language=language
            )
            log.info(f"Info scraped for id {id}: {res._movie_name}")
        except HTTPError as e:
            if e.response.reason == 'Too Many Requests' and e.response.status_code == 429:
                log.info(f'Too many requests to TMDB. Waiting limit refreshment: {id.title} {id.year}')
                sleep(float(e.response.headers._store['retry-after'][1]) + 0.1)
            else:
                log.info(f"Something wrong getting info from TMDB:{id.title} {id.year}")
                return None
        except Exception as e:
            #TODO: check if id doesn't exist what exception is raised
            pass
    if res:
        return res
    else:
        return None

API_KEY = "9ef710d4561ef740d1e11316dd5f94c5"
tmdb_client = TMDBClient(API_KEY)


def kk(ids_file_path):
    with open(ids_file_path, 'r') as f:
        ids = f.readlines()
        for id in ids:
            tvs = [tmdb_client.find_all_tv_episodes(int(id)) for id in ids]

MAX_APPENDS = 20

def get_episode_by_tv_ids(limit, language=None, storage_url=None, file_with_ids="tv_show_ids.txt"):
    #tmdb_client.TV(tv_show_id) accepts as str as int
    tv_show_ids = read_tv_ids_from_file(filename=file_with_ids)
    return _get_episode_by_tv_ids(tv_show_ids, limit, language, storage_url)

def _get_episode_by_tv_ids(tv_show_ids, limit, language, storage_url):
    '''
    Here new approach. get_episodes_by_tv_show_id can raise exceptions instead of returning None what shows that there was
    a problem.
    Gets info from TMDB and IMDB. Also makes translation (inside TVEpisode.__init__())
    :param tv_show_ids
    :param storage_url: from args.url
    :param limit: from args.limit
    :param language: from args.language
    :return: [episod_info]
    '''
    with concurrent.futures.ThreadPoolExecutor() as executor:
        #bring out or leave inside (read from file)
        retrieved_episodes = []
        future_to_tv_id = {executor.submit(get_episodes_by_tv_show_id, tv_id, limit, language, storage_url): tv_id for tv_id in tv_show_ids}
        for future in concurrent.futures.as_completed(future_to_tv_id):
            tv_id = future_to_tv_id[future]
            try:
                retrieved_episodes.extend(future.result())
            except Exception as e:
                error_log.error(f"Failed to get info for:{tv_id}: {e}")
                log.info(f"Failed to get info for:{tv_id}: {e}")
        return retrieved_episodes


def _make_append_to_response_strings(tv_show_id):
    tv_info = tmdb.TV(tv_show_id).info()
    seasons_count = len(tv_info['seasons'])
    start_season_num = tv_info['seasons'][0]['season_number']
    append_to_response = []
    left_seasons = seasons_count
    while left_seasons >= 0:
        if left_seasons >= MAX_APPENDS:
            append_to_response.append(['season/' + str(start_season_num + i) for i in range(0, 21)])
            left_seasons -= 20
        else:
            append_string = ['season/' + str(start_season_num + i) for i in range(0, left_seasons)]
            append_string.append('credits')
            append_to_response.append(append_string)
            break
            #left_seasons = 0
    return append_to_response

def get_episodes_by_tv_show_id(tv_show_id, limit=None, language=None, storage_url=None):
    '''
    requests TMDB for count of seasons, builds append_to_response=[['season/1','season/2',..,'season/20'],[..],['season/40',..,'credits']
    (each not longer 20-limitation of TMDB) and extracts episode infos from responses
    :param tv_show_id: tmdb id
    :param imdb_tv_info: imdb info with all episodes (required pre client.update(imdb_tv_info, 'episodes'))
    :return: list of TVEpisode
    '''
    append_to_response = _make_append_to_response_strings(tv_show_id)
    res = []
    imdb_client = None
    for seasons_chunk in append_to_response:
        # to make string for append_to_response='season/1,season/2,credits'
        response = tmdb.TV(tv_show_id).info(append_to_response=','.join(seasons_chunk))
        tmdb_tv_show_name = response['name']
        tmdb_tv_show_credits = response['credits']
        #Get IMDB info - episodes and common info for TV show
        if imdb_client is None:
            imdb_client = IMDb(loggingLevel=IMDb_LOGGING_LEVEL)
            imdb_id = imdb_client.search_movie(tmdb_tv_show_name)[0].movieID
            imdb_tv_info = imdb_client.get_movie(imdb_id)
            imdb_client.update(imdb_tv_info, 'episodes')
            companies = imdb_tv_info['production companies']
            runtimes = None
            if imdb_tv_info['runtimes'][0]:
                runtimes = imdb_tv_info['runtimes'][0]
            genres = imdb_tv_info['genres']
            countries = imdb_tv_info['countries']
            languages = imdb_tv_info['languages']
            producers = None
            if 'producers' in imdb_tv_info:
                producers = imdb_tv_info['producers']

        if 'credits' in seasons_chunk:
            seasons_chunk.remove('credits')
        for season in seasons_chunk:
            #season_num = int(season.split('/')[1])
            for ep in response[season]['episodes']:
                season_num = ep['season_number']
                episode_num = ep['episode_number']
                ep_credits = {
                    'cast': tmdb_tv_show_credits['cast'],
                    'crew': ep['crew'],
                    'guest_stars': ep['guest_stars']
                }
                try:
                    ep_year = imdb_tv_info['episodes'][season_num][episode_num].data['year']
                    # get info and credits from tmdb
                    credits = ep_credits
                    tmdb_info = ep
                    # TODO: move to the end after IMDb
                    episode_info = TVEpisode(
                        tmdb_tv_show_name,
                        tmdb_info,
                        credits,
                        link=None,
                        storage_url=storage_url,
                        limit=limit,
                        language=language,
                        companies=companies,
                        year=ep_year,
                        runtime=runtimes,
                        genres=genres,
                        countries=countries,
                        languages=languages,
                        producers=producers
                    )
                    res.append(episode_info)
                #case when tmdb and imdb seasons/episodes don't correspond to each other (for instance imdb doesn't have season 0 - specials)
                except KeyError as e:
                    error_log.error(f"No info on imdb for tmdb id: {tv_show_id} : {response['name']} Season {season_num} Episode {episode_num}")
                    continue

        #raise e#Exception(f"Failed to get info from TMDB for: {tv_show_id}")
    return res