"""Reads movies/tvs which must be posted to wordpress sites. It can be listed in local files or on remote webserver"""

import json
import re
from types import SimpleNamespace as Namespace
from urllib.parse import unquote

import requests_html
from fuzzywuzzy import fuzz
from natsort import natsorted, ns


class Episode:
    def __init__(self, episode_title, season_num, ep_num, link):
        self.episode_title = episode_title
        self.season_num = season_num
        self.ep_num = ep_num
        self.link = link
        self._episode_line = f"{self.episode_title} Season {self.season_num} Episode {self.ep_num}"

    def __eq__(self, other):
        return self.episode_title == other.episode_title and \
               self.season_num == other.season_num and \
               self.ep_num == other.ep_num

    def __ne__(self, other):
        return self.episode_title != other.episode_title or \
               self.season_num != other.season_num or \
               self.ep_num != other.ep_num

    def __hash__(self):
        return (self.episode_title, self.season_num, self.ep_num).__hash__()

    def __str__(self):
        return self._episode_line




def read_movies_from_file(filename="_movies.txt"):
    with open(filename, "r") as f:
        return f.readlines()


def read_episodes_from_file(filename="tv_episodes.txt"):
    with open(filename, "r") as f:
        return f.readlines()


def read_movie_ids_from_file(filename="movie_ids.txt"):
    with open(filename, "r") as f:
        return f.read().splitlines()


def read_tv_ids_from_file(filename="tv_show_ids.txt"):
    with open(filename, "r") as f:
        return f.read().splitlines()


def parse_episodes(episode_lines, from_storage=False):
    """ Parsing _episodes from file, preferable format: SerialName|seasonNumber|episodeNumber
    :type filename: str
    :rtype: list of _episodes
    """
    episodes = []
    if from_storage:
        for line in episode_lines:
            line, link = line
            episode, season, episode_num = parse_episode_info(line)
            # _episodes[episode] = [season, episode_num, link]
            episodes.append(Episode(episode, season, episode_num, link))
    else:
        for line in episode_lines:
            episode, season, episode_num = parse_episode_info(line.strip())
            episodes.append(Episode(episode, season, episode_num, None))
    return episodes


def parse_episode_info(line):
    """
    Parse episode line from 
    Serial Season X Episode Y
    to
    [Serial, X, Y]
    """
    episode = line.strip()
    name = episode.split("Season")[0].strip()
    season_num, ep_num = [
        x.strip() for x in episode.split("Season")[1].split("Episode")
    ]
    return name, int(season_num), int(ep_num)


def parse_movie_info(line):

    movie = line.strip()
    movie_info = extract_movie_info(movie)
    year = None
    if movie_info:
        movie = movie_info.group()[:-4].strip()
        year = movie_info.group(2)[-4:].strip()
    if not movie and year:
        movie, year = year, None
    return movie, year


def parse_movies(movie_lines, from_storage=False):
    """ Parsing _movies from file, preferable format: MovieName year
    :type filename: str
    :rtype: list of _movies
    """
    movies = {}
    if from_storage:
        for line in movie_lines:
            line, link = line
            movie, year = parse_movie_info(line)
            movies[movie] = [year, link]
    else:
        for line in movie_lines:
            movie, year = parse_movie_info(line)
            movies[movie] = [year, None]
    return movies


def clean_link(link):
    """
    Remove dots, split, and group link
    """
    match = extract_movie_info(link)
    if match:
        link = match.group().replace(".", " ")
    else:
        link = ' '.join(re.split(r'\.|\s', link)[:-3])
        #delete: replaced with above
        # link = " ".join(link.replace(".", " ").split(" ")[:-3])

    return link.strip()


def calc_ratio(movie, other):
    """
    Calculate 'equality' of the string
    """
    return fuzz.ratio(movie, other)


def extract_movie_info(line):
    line = re.sub(r"(\(|\))", "", line)
    rg = re.compile(
        ".*([\[\(]?((?:19[0-9]|20[01])[0-9])[\]\)]?)", re.IGNORECASE | re.DOTALL
    )
    return rg.search(line)


def get_links_from_storage(url="https://www.google.com/"):
    """
    Gets links from storage
    """
    session = requests_html.HTMLSession()
    response = session.get(url, timeout=10)
    links = response.html.links
    return links

#TODO: remake that shit. Precisely clean_episode_link is done to fit following usage of results
def parse_episodes_from_storage(url="https://www.google.com/"):
    """
    Filter and sorting links for _episodes
    """
    links = get_links_from_storage(url)
    links = filter(lambda x: "/" not in x and "C=" not in x, links)
    links = natsorted(links, alg=ns.IGNORECASE)
    links = [(clean_episode_link(unquote(link)), link) for link in links]
    return [[cleaned_link, f"{url}{link}"] for (cleaned_link, link) in links if cleaned_link is not None]
    #delete: replaced with above
    #return [[clean_episode_link(unquote(link)), f"{url}{link}"] for link in links]


def clean_episode_link(link):
    match = re.search(r'(?P<title>.+)\.Season\.(?P<season_num>\d+)\.Episode\.(?P<ep_num>\d+)\.(.+)', link)
    if match:
        groups = match.groupdict()
        res = f'{groups["title"].replace("."," ")} Season {groups["season_num"]} Episode {groups["ep_num"]}'
        return res
    else:
        return None
    #delete: replaced with above
    #return link[: link.find(".")]


def parse_movies_from_storage(url="https://www.google.com/"):
    """
    Filter and sorting links for _movies
    """
    links = get_links_from_storage(url)
    sorted_links = sorted(links)
    links = filter(lambda x: "/" not in x and "C=" not in x, sorted_links)
    return [[clean_link(unquote(link)), f"{url}{link}"] for link in links]


def json_to_obj(json_obj):
    """
    Converting json dict to Python object
    so instead of doing json_obj.get("data") you can just do json_obg.data
    """
    data = json.dumps(json_obj)
    return json.loads(data, object_hook=lambda d: Namespace(**d))



