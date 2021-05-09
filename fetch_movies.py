"""Main module to upload movies with info to wordpress sites. Reads from file which movies must be uploaded, get info
from IMDB, TMDB, makes translation to required languages via Yandex translater and saves which movies were processed to
csv file representing database."""

import logging
import sys
import traceback
from collections import namedtuple

import api
import wp
from argparser import argparser_movies
import db
from helpers import (
    calc_ratio,
    parse_movies,
    parse_movies_from_storage,
    read_movies_from_file
)
from wp import get_wps
from movie import Movie, WPMovie
import concurrent.futures



def is_on_site(cur_movies, movie_title, movie_year):
    movie_title = movie_title.lower()
    for movie in cur_movies:
        cur_movie_title = movie.title
        cur_movie_year = movie.year
        # log.info(f"Year: {cur_movie_year}, {movie_year}")
        ratio = calc_ratio(cur_movie_title, movie_title)
        if ratio == 100 or (ratio >= 90 and cur_movie_year == movie_year):
            return True
        else:
            if ratio > 80:
                log.info(
                    f"{cur_movie_title}, {movie_title} - {calc_ratio(cur_movie_title, movie_title)}"
                )
                log.info(
                    f"{cur_movie_title} == {movie_title} - {cur_movie_title == movie_title}"
                )
    return False

#delete
# def post_to_wps(wps_content: wp.WP_Content, movie: Movie):
#     '''Concurrently posts movie to wp_clients logging raised exceptions'''
#     with concurrent.futures.ThreadPoolExecutor() as executor:
#         movie_to_post = movie.to_post()
#         future2wp_content = {executor.submit(wp_client.post_movie, movie_to_post): wp_client for wp_client, _ in wps_content}
#         for future in concurrent.futures.as_completed(future2wp_content):
#             cur_exc = future.exception()
#             if cur_exc is not None:
#                 log.exception(f"{future2wp_content[future].client.url} returned exception {cur_exc} while wp_client.post_movie")


logging.basicConfig(
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
    format="%(asctime)s [%(filename)s:%(lineno)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/movies_logs.log", encoding='UTF-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger()


def main():
    parser = argparser_movies()
    args = parser.parse_args()
    all_wp_clients = get_wps(args.wps)
    # Setting argparser and read args
    if args.just_url:
        log.info("Using just URL option.")
        movie_lines = parse_movies_from_storage(args.just_url)
        movies = parse_movies(movie_lines, from_storage=True)
        storage_url = args.just_url
    if args.file:
        log.info("Using url + file option.")
        storage_url = args.url
        file_with_movies = args.file
        movie_lines = read_movies_from_file(file_with_movies)
        movies = parse_movies(movie_lines)

    movie_infos = []
    if movies:
        movies = [WPMovie(movie_title, year,link) for movie_title, [year, link] in movies.items()]
        #leave only movies which must be posted to any wp. Not to post (upload) already uploaded movies
        missing_movies = db.DataBaseManager.get_movies_to_upload(movies, all_wp_clients)
        if not missing_movies:
            log.info("There is nothing to upload. All wp sites have provided movies")
            return
        db.log_filtered_objs(movies, missing_movies)
        movie_infos = api.get_movie_infos(missing_movies, storage_url, args.limit, args.language)
    if args.ids:
        log.info("Using -ids option")
        m = api.get_movie_infos_by_id(args.ids, args.url, args.limit, args.language)
        missing_movies = db.DataBaseManager.get_movies_to_upload(m, all_wp_clients)
        movie_infos.extend(missing_movies)

    wp2posted_movies = wp.WordPressCollection.post_movies(all_wp_clients, movie_infos)
    db.DataBaseManager.write_movies_to_csv(wp2posted_movies)

if __name__ == '__main__':
    main()