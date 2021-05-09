"""Argparsers creation for movies and shows. Reads movie or show names from some file, then reads wordpress sites with
their credentials where to upload."""

import argparse


def argparser_movies():
    parser = argparse.ArgumentParser(
        description="Fetch data from TMDB and post it on WordPress website"
    )
    #TODO: return required=True if needed to -d, -U, -p
    parser.add_argument("-d", "--domain", help="Specify WP domain url.", required=False)
    parser.add_argument("-U", "--username", help="Specify WP username.", required=False)
    parser.add_argument("-p", "--password", help="Specify WP username.", required=False)
    parser.add_argument(
        "-u",
        "--url",
        help="Storage url to scrape filenames",
        default="https://www1.watchgames.online/test",
        required=False,
    )
    parser.add_argument(
        "-f", "--file", help="File with _movies", nargs='?', const="_movies.txt", required=False
    )
    parser.add_argument("-j", "--just_url", help="Just url flag", required=False)
    #    parser.add_argument("-a", "--actors_count",
    #                        help="Specify actors count", required=False)
    parser.add_argument(
        "-l", "--limit", help="Set limit for all fields", required=False
    )
    parser.add_argument(
        "-lang", "--language", help="Set language", required=False
    )
    parser.add_argument(
        "-wps", help="Set path to file where urls of word press web sites are listed", required=False
    )
    parser.add_argument(
        "-ids", help="Set path to file with ids of tv shows to upload to wps", required=False,
        nargs='?',
        const="movie_ids.txt"
        #action='store_true'
    )
    return parser


def argparser_tv():
    parser = argparse.ArgumentParser(
        description="Fetch data from TMDB and post it on WordPress website"
    )
    parser.add_argument("-d", "--domain", help="Specify WP domain url.", required=False)
    parser.add_argument("-U", "--username", help="Specify WP username.", required=False)
    parser.add_argument("-p", "--password", help="Specify WP username.", required=False)

    parser.add_argument(
        "-u",
        "--url",
        help="Storage url to scrape filenames",
        default="https://www1.watchgames.online/test",
        required=False,
    )
    parser.add_argument(
        "-f",
        "--file",
        nargs='?',#allows to proved 0-1 arguments. if -f is not used it takes default, if used without arguments then takes <const> value
        help="File with tv _episodes",
        const="tv_episodes.txt",
        required=False,
    )
    parser.add_argument("-j", "--just_url", help="Just url flag", required=False)
    #    parser.add_argument("-a", "--actors_count",
    #                        help="Specify actors count", required=False)
    parser.add_argument(
        "-l", "--limit", help="Set limit for all fields", required=False
    )
    parser.add_argument(
        "-lang", "--language", help="Set language", required=False
    )
    parser.add_argument(
        "-wps", help="Set path to file where urls of word press web sites are listed", required=False,
        nargs='?',
        const='wps_info.txt'
    )
    parser.add_argument(
        "-ids", help="Set path to file with ids of tv shows to upload to wps", required=False,
        nargs='?',
        const="tv_show_ids.txt"
        #action='store_true'
    )
    return parser
