"""Main module to upload tvs with info to wordpress sites. Reads from file which tvs must be uploaded, get info
from IMDB, TMDB, makes translation to required languages via Yandex translater and saves which movies were processed to
csv file representing database."""

import logging
import sys
import traceback
from requests.exceptions import HTTPError
import api
import wp
from argparser import argparser_tv
from helpers import (
    parse_episodes,
    parse_episodes_from_storage,
    get_links_from_storage,
    read_episodes_from_file,
    calc_ratio
)
from wp import get_wps
from db import DataBaseManager, log_filtered_objs
from tv import TVEpisode
import pandas as pd
from natsort import natsorted, ns


def main():
    logging.basicConfig(
        # level=logging.INFO,
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
        format="%(asctime)s [%(filename)s:%(lineno)s] %(message)s",
        handlers=[
            logging.FileHandler("logs/tv_logs.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger()
    parser = argparser_tv()
    args = parser.parse_args()

    all_wp_clients = get_wps(args.wps)
    episodes = None
    #Setting argparser and read args
    if args.just_url:
        log.info("Using just URL option.")
        episode_lines = parse_episodes_from_storage(args.just_url)
        # log.info(episode_lines)
        episodes = parse_episodes(episode_lines, from_storage=True)
        storage_url = args.just_url
    if args.file:
        log.info("Using url + file option.")
        storage_url = args.url
        file_with_tv = args.file
        episode_lines = read_episodes_from_file(file_with_tv)
        episodes = parse_episodes(episode_lines)
    #list of TVEpisode with all collected info from TMDB, IMDB ready to post
    episode_infos_to_post = []
    if episodes:
        # just list of Episode (no internal infos) that are not on WP sites
        missing_episodes = DataBaseManager.get_episodes_to_upload(episodes, all_wp_clients)
        log_filtered_objs(episodes, missing_episodes)
        if missing_episodes:
            # Uncomment after debug
            episode_infos_to_post = api.get_episode_infos(missing_episodes, storage_url, args.limit, args.language)
        else:
            log.info("There is nothing to upload. All wp sites have provided movies")
            # return

    if args.ids:
        eps = api.get_episode_by_tv_ids(args.limit, args.language, args.url, file_with_ids=args.ids)
        missing_episodes = DataBaseManager.get_episodes_to_upload(eps, all_wp_clients)
        episode_infos_to_post.extend(missing_episodes)

    wp2posted_eps = wp.WordPressCollection.post_episodes(all_wp_clients, episode_infos_to_post)
    DataBaseManager.write_episodes_to_csv(wp2posted_eps)

if __name__ == '__main__':
    main()