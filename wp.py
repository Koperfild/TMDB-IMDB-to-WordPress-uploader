"""WordPress and WordPressCollection to make new posts or receive information about already posted movies/tvs"""

import json
import logging
import os
from collections import namedtuple
import wget
from wordpress_xmlrpc import Client, WordPressPost, ServerConnectionError
from wordpress_xmlrpc.compat import xmlrpc_client
from wordpress_xmlrpc.methods import media, posts
import concurrent
import time
from xmlrpc.client import ProtocolError
import random
import http
from db import DataBaseManager
import socket
import xmlrpc.client
import os, glob
import re

from movie import WPMovie
from threading import Lock
from loggers import error_log

log = logging.getLogger(__name__)
WP_Content = namedtuple("WP_Content", ["client", "wp_movies"])
TMP_IMG_FOLDER = os.path.join(os.getcwd(), "tmp")
#TMDB has limit of 40 requests for 10 seconds

TMDB_RATELIMIT = 40
ATTEMPTS_LIM = 5
lock_get_client = Lock()
DOWNLOADED_IMAGES = {}

if not os.path.exists(TMP_IMG_FOLDER):
    os.mkdir(TMP_IMG_FOLDER)



#delete 2 lines if not required
lock = Lock()

class DownloadImageError(Exception):
    pass

class ConnectionError(Exception):
    pass

CUSTOM_KEYS = {"description", "movie_first_url", "poster_url", "runtime"}

CUSTOM_KEYS_EP = {
    "description",
    "season",
    "episode",
    "movie_first_url",
    "poster_url",
    "runtime",
}

TERM_NAMES_EP = {
    "season",
    "series",
    "tvshow_writer",
    "tvshow_producer",
    "tvshow_director",
    "tvshow_actors",
    "tvshow_company",
    "tvshow_language",
    "tvshow_country",
    "tvshow_genre",
    "tvshow_year",
}

TERM_NAMES = {
    "writer",
    "mpaaratings",
    "language",
    "company",
    "producer",
    "director",
    "country",
    "movie_year",
    "movie_genre",
    "actors",
}


#TODO: ideally implement downloading of all images concurrently out of self.post_episode.
#So will be download images-> upload images-> post
def download_img(url, filename):
    """ Downloading img from the following url and save it as filename, return filename
    :type url: str
    :param url: url of the img
    :type filename: str
    :return absolute filepath of saved file
    """
    if url in DOWNLOADED_IMAGES:
        return DOWNLOADED_IMAGES[url]
    #delete: replaced with lock
    # #instead of lock we say that url is being processed. If downloading will fail we have problems
    # #DOWNLOADED_IMAGES[url] = None
    log.info(f"Downloading image for {filename}...")
    is_error = True
    attempts_num = 0
    while is_error and attempts_num <= ATTEMPTS_LIM:
        try:
            attempts_num += 1
            #TODO: it's better to use UIID instead of filename
            f_modified = re.sub('[\/^:*?"<>|]', ' ', filename)
            file_path = wget.download(url, out=os.path.join(TMP_IMG_FOLDER, f"{f_modified}.jpg"), bar=None)
            is_error = False
        except Exception as e:
            time.sleep(random.uniform(0.5, 2))
            log.error(f'Retrying downloading {filename}')

    if is_error:
        raise DownloadImageError(f'Error downloading image: {filename}'. Skipping)
    #delete replaced file name on absolute path
    #filename = filename.replace("/", "|")
    DOWNLOADED_IMAGES[url] = file_path
    return file_path


def remove_imgs():
    """
    Just removing all .jpg files in the current directory
    """
    # DOWNLOADED_IMAGES.clear()
    img_files_mask = "*.jpg"
    tmp_imgs = os.path.join(os.getcwd(),'tmp', img_files_mask)
    for f in glob.glob(tmp_imgs):
        os.remove(f)


class WordPressCollection:
    """To work with collection of WordPress (look below) instances"""
    @staticmethod
    def get_current_movies(wp_clients):
        '''
        fills self._movies for each wp_client
        :param wp_clients:
        :return:
        '''
        # await asyncio.gather(*[wp_client.get_current_movies() for wp_client in wp_clients])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            return list(executor.map(WordPress.get_current_movies, wp_clients))

    @staticmethod
    def get_current_episodes(wp_clients):
        '''
        fills self._episodes for each wp_client
        :param wp_clients:
        :return:
        '''
        #asyncio.gather(*[wp_client.get_current_episodes() for wp_client in wp_clients])
        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(WordPress.get_current_episodes, wp_clients)

    @staticmethod
    def filter_episode_names_to_upload(episodes_to_upload, wp_clients):
        '''

        :param episodes: [helpers.Episode,..]
        :return: [helpers.Episode,..]
        '''
        #We subtract from episodes_to_upload intersection of movies from all wps.
        episodes_not_to_upload = set.intersection(*[{wp_client._episodes} for wp_client in wp_clients])
        #remove None from set
        episodes_not_to_upload -= {None}
        [log.info(f"{ep.episode} {ep.season_num} {ep.ep_num} is already on all sites. Skipping") for ep in episodes_not_to_upload]
        return {*episodes_to_upload} - episodes_not_to_upload

    @staticmethod
    def post_episodes(wp_clients, episodes):
        if not episodes:
            log.info("No episodes to upload")
            return
        with concurrent.futures.ThreadPoolExecutor() as executor:
            wp2processed_eps = {}
            try:
                for wp, processed_eps in zip(wp_clients, executor.map(lambda wp_client: wp_client.post_episodes(episodes), wp_clients)):
                    #exclude eps which raised exceptions and were not posted
                    processed_eps = [ep for ep in processed_eps if ep is not None]
                    wp2processed_eps[wp] = processed_eps
            finally:
                WordPress.dispose()
                return wp2processed_eps
        #delete: replaced with above
        # asyncio.gather(*[wp_client.post_episodes(episodes) for wp_client in wp_clients])

    @staticmethod
    def post_movies(wp_clients, movies):
        if not movies:
            log.info("No movies to upload")
            return
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            wp2processed_movies = {}
            try:
                for wp, processed_movies in zip(wp_clients,
                                             executor.map(lambda wp_client: wp_client.post_movies(movies),
                                                          wp_clients)):
                    # exclude eps which raised exceptions and were not posted
                    processed_movies = [movie for movie in processed_movies if movie is not None]
                    wp2processed_movies[wp] = processed_movies
            finally:
                WordPress.dispose()
                return wp2processed_movies

class WordPress:
    #TODO: during init might be required to self.get_current_movies and/or self.get_current_episodes
    def __init__(self, url, username, password, tags):
        self.url = url
        self.username = username
        self.password = password
        #delete if replacement by get_client() is ok
        # self.client = Client(url=url, username=username,
        #                      password=password, blog_id=1)
        self.tags = tags
        self._movies = None
        self._episodes = None

    def get_client(self, timeout=15):
        #Prevent hanging while uploading post and picture to wp
        with lock_get_client:
            transport = xmlrpc.client.SafeTransport()
            conn = transport.make_connection(self.url.lstrip('https://'))
            conn.timeout = timeout
            client = Client(url=self.url, username=self.username,password=self.password, blog_id=1, transport=transport)
            return client

    @staticmethod
    def dispose():
        remove_imgs()

    def get_current_movies(self):
        if self._movies is not None:
            return self._movies
        else:
            self._load_current_movies()


    def _load_current_movies(self):
        log.info(f"Fetching _movies from site {self.url} to avoid duplicates...")
        movies = []
        offset = 0
        increment = 100
        while True:
            data = self.get_client().call(
                posts.GetPosts(
                    {"post_type": "movies", "number": increment, "offset": offset}
                )
            )
            if not data:
                break

            for post in data:
                title = post.title.strip().lower()
                year = None
                for term in post.terms:
                    if term.taxonomy == "movie_year":
                        year = term.name
                movies.append(WPMovie(title, year))

            offset = offset + increment
        log.info(f"Fetching _movies for {self.url} is done.")
        self._movies = movies




    def get_current_episodes(self):
        if self._episodes is not None:
            return
        else:
            self._load_current_episodes()


    def _load_current_episodes(self):
        log.info(f"Fetching tvshows from {self.url} to avoid duplicates...")
        tv_shows = []
        offset = 0
        increment = 100
        while True:
            data = self.get_client().call(
                posts.GetPosts(
                    {"post_type": "tvshows", "number": increment, "offset": offset}
                )
            )
            if not data:
                break
            tv_shows.extend([post.title for post in data])
            offset = offset + increment
        #TODO: check format of tv_shows to adjust according self._episodes which is of type helpers.Episode
        raise Exception
        self._episodes = tv_shows
        log.info(f"Fetching tvshows from {self.url} is done.")





    #delete:
    # async def has_episodes(self, episodes):
    #     episodes = {f"{ep.episode} Season {ep.season_num} Episode {ep.ep_num}" for ep in episodes}
    #     episodes.intersection(self._episodes)

    #delete: if not required
    # async def has_episode(self, tv_name, season_num, episode_num):
    #     '''
    #     Checks whether wp contains episode.
    #     :return: True if found. None if not found or EPISODES WERE NOT LOADED by self.get_current_episodes
    #     '''
    #     episode_title = f"{tv_name} Season {season_num} Episode {episode_num}"
    #     if self._episodes is not None and\
    #         episode_title in self._episodes:
    #         return True
    #     return False


    def fill_post(self, post, movie_info, post_type, custom_keys, term_names):
        """ Fill post with movie info
        :type post: WordPressPost

        :type movie_info: Movie
        """
        post.post_type = post_type
        post.comment_status = 'open'
        post.title = movie_info.get("title")
        post.custom_fields = []
        for key in custom_keys:
            post.custom_fields.append(
                {"key": key, "value": f"{movie_info.get(key)}"})
        # post.terms_names = {
        #     'actors': movie_info.get('actors'),
        #     'company': movie_info.get('company'),
        #     'director': movie_info.get('director'),
        #     'language': movie_info.get('language'),
        #     'movie_genre': movie_info.get('movie_genre'),
        #     'movie_year': movie_info.get('movie_year'),
        #     'mpaaratings': movie_info.get('mpaaratings'),
        #     'producer': movie_info.get('producer'),
        #     'writer': movie_info.get('writer')
        # }
        post.terms_names = {}
        post.terms_names['post_tag'] = self.tags
        post.terms_names['post_tag'].append(f"{movie_info.get('title')}")	
        post.terms_names['post_tag'].append(f"{movie_info.get('title')} ({movie_info.get('movie_year', [2019])[0]})")	
        # post.terms_names['post_tag'].append(f"{movie_info.get('title')} bmovies")
        # post.terms_names['post_tag'].append(f"{movie_info.get('title')} bmovies _movies")
        for term_name in term_names:
            post.terms_names[term_name] = movie_info.get(term_name)


    def upload_image(self, post, img_url):
        """ Download image and upload it on WP as attachment to post
        :type post: WordPressPost

        :type img_url: str
        """
        ################################Change post.title to english title
        with lock:
            file_path = download_img(img_url, post.title)

        data = {"name": f"{file_path}", "type": "image/jpeg"}

        with open(file_path, "rb") as img:
            data["bits"] = xmlrpc_client.Binary(img.read())
        is_error = True
        attempts_num = 0
        while is_error and attempts_num <= ATTEMPTS_LIM:
            try:
                attempts_num += 1
                response = self.get_client().call(media.UploadFile(data))
                is_error = False
            except (ServerConnectionError, ProtocolError, http.client.CannotSendRequest, http.client.ResponseNotReady,
                    http.client.CannotSendHeader) as e:
                time.sleep(random.uniform(1, 3))
            except socket.timeout as e:
                log.info(f"Error uploading to {self.url}: {post.title}. Retrying")
        if is_error and attempts_num > ATTEMPTS_LIM:
            log.error(f'Problem uploading image to {self.url}: {post.title}. Skipping')
            raise ConnectionError(f'Problem uploading post to {self.url}: {post.title}. Skipping')
        attachment_id = response["id"]
        post.post_status = "publish"
        post.thumbnail = attachment_id
        is_error = True
        attempts_num = 0
        while is_error and attempts_num <= ATTEMPTS_LIM:
            try:
                attempts_num += 1
                post.id = self.get_client().call(posts.NewPost(post))
                log.info(f"Image {file_path} uploaded to {self.url}.")
                is_error = False
            except (ServerConnectionError, ProtocolError, http.client.CannotSendRequest, http.client.ResponseNotReady,
                    http.client.CannotSendHeader) as e:
                time.sleep(random.uniform(1, 3))
            except socket.timeout as e:
                log.info(f'Problem uploading image to {self.url}: {post.title}. Retrying')
                time.sleep(random.uniform(2,6))
        if is_error and attempts_num > ATTEMPTS_LIM:
            # log.error(f'Problem uploading image to {self.url}: {post.title}')
            raise ConnectionError(f'Problem uploading image to {self.url}: {post.title}')

    def post(self, post):
        """ Upload post to wp
        :type post: WordPressPost
        """
        #TODO: maybe required to make counter and make not more then 10-15 attempts not to loop forever
        log.info(f"Publishing to {self.url}: {post.title} ...")
        is_error = True
        attempts_num = 0
        while is_error and attempts_num <= ATTEMPTS_LIM:
            try:
                attempts_num += 1
                self.get_client().call(posts.EditPost(post.id, post))
                is_error = False
                log.info(f"Published to {self.url}: {post.title}")
            except (ServerConnectionError, ProtocolError, http.client.CannotSendRequest, http.client.ResponseNotReady,
                    http.client.CannotSendHeader) as e:
                time.sleep(random.uniform(1, 3))
            except socket.timeout as e:
                log.info("some error")
        if is_error and attempts_num > ATTEMPTS_LIM:
            log.error(f'Problem uploading post to {self.url}: {post.title}')
            raise ConnectionError(f'Problem uploading post to {self.url}: {post.title}')


    def post_movies(self, movies):
        '''
        Posts episodes to WP asyncronously for each episode.
        self._episodes must be prefilled
        :param movies: [tv.TVEpisode,..]
        :return:
        '''
        #filter episodes for only this wp
        movies = DataBaseManager.get_movies_to_upload(movies, [self])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            processed_movies = []
            try:
                for movie, _ in zip(movies, executor.map(lambda movie: self.post_movie(movie.to_post()), movies)):
                    if _ is not None:
                        processed_movies.append(movie)
            except Exception as e:
                log.info("Error")
                pass
            finally:
                return processed_movies


    def post_movie(self, movie):
        """ Full process of posting a movie as a post to WP
        :type movie: Movie
        """
        try:
            post = WordPressPost()
            self.fill_post(
                post,
                movie,
                post_type="movies",
                custom_keys=CUSTOM_KEYS,
                term_names=TERM_NAMES
            )
            self.upload_image(post, movie.get("img"))
            self.post(post)
            return movie
        except Exception as e:
            log.exception(f"Exception while posting movie to {self.url}.")
            error_log.error(f"{movie._episode_line} to {self.url}: {e}")
            return None

    def post_episodes(self, episodes):
        '''
        Posts episodes to WP asyncronously for each episode.
        self._episodes must be prefilled
        :param episodes: [tv.TVEpisode,..] Episodes that are not presented at any wp
        :return:
        '''
        #filter episodes for only this wp
        episodes = DataBaseManager.get_episodes_to_upload(episodes, [self])
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            processed_episodes = []
            try:
                for episode, _ in zip(episodes, executor.map(lambda ep: self.post_episode(ep.to_post()), episodes)):
                    if _ is not None:
                        processed_episodes.append(episode)
            except Exception as e:
                error_log.error(e)
                log.info(f"Error {e}")
                pass
            finally:
                return processed_episodes


    def post_episode(self, movie):
        """ Full process of posting a episode as a post to WP
        :type movie: TVEpisode
        :return returning movie means it was published. None - any failure for executor.map not to interrupt in case of raising exception
        """
        try:
            post = WordPressPost()
            self.fill_post(
                post,
                movie,
                post_type="tvshows",
                custom_keys=CUSTOM_KEYS_EP,
                term_names=TERM_NAMES_EP
            )
            self.upload_image(post, movie.get("img"))
            self.post(post)
            # log.info(f"{movie['title']} was posted to {self.url}")
            return movie
        except Exception as e:
            #TODO Check whether property movie._episode_line exists
            log.exception(f"Exception while posting episode {movie._episode_line}\n{e}")
            error_log.error(f"{movie._episode_line} to {self.url}: {e}")
            return None


def read_wps_info_from_file(filename="wps_info.txt"):
    with open(filename, 'r') as f:
        return json.load(f)


def get_wps(file_path="wps_info.txt"):
    wps_info = read_wps_info_from_file(file_path)
    return [WordPress(f"{wp_info['url']}xmlrpc.php", wp_info['user'], wp_info['password'], wp_info['tags']) for wp_info in wps_info]