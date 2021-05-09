"""TVEpisode class to request, store, and process (translate and so on) tvepisode info. """

import logging
from urllib.parse import unquote

from fuzzywuzzy import fuzz
from requests_html import HTMLSession

from helpers import json_to_obj
from translate import make_translations

log = logging.getLogger(__name__)


def remove_trash(url):
    """ 
    Removing trash from tv url on storage
    """
    return unquote(url[: url.find(".")])


class TVEpisode:
    def __init__(
        self,
        tv_show_name,
        info,#response from tmdb .info()
        credits,#response from tmdb .credits(). One can use append_to_response to reduce amount of requests to tmdb
        link=None,
        storage_url=None,
        limit=None,
        language=None,
        companies = [],
        year = None,
        runtime = [],
        genres = [],
        countries = [],
        languages = [],
        producers = []
    ):
        '''
        :param language: If not provided None means no translations
        :param info: One can use append_to_response to reduce amount of requests to tmdb https://developers.themoviedb.org/3/getting-started/append-to-response
        :param credits: One can use append_to_response to reduce amount of requests to tmdb https://developers.themoviedb.org/3/getting-started/append-to-response
        '''
        #delete d
        # log.info("before episode.info")
        #delete
        #synchronize_TMDB()
        #TODO: check whether it works
        info = json_to_obj(info)
        credits = json_to_obj(credits)
        season_num = info.season_number
        episode_num = info.episode_number
        if language is not None:
            log.info(f'Translating:{tv_show_name} Season {season_num} Episode {episode_num}')
            make_translations(credits.cast, credits.crew, target_lang=language, source_lang='auto')
            log.info(f'Translated:{tv_show_name} Season {season_num} Episode {episode_num}')
        self._link = link
        self._serial_name = tv_show_name
        self._episode_line = f"{tv_show_name} Season {season_num} Episode {episode_num}"
        self._series = f"{tv_show_name} Season {season_num}"
        self._season_num = season_num
        self._episode_num = episode_num
        self._limit = limit
        self._storage_url = storage_url
        self._title = info.name
        self._cast = credits.cast
        self._crew = credits.crew
        self._img_url = info.still_path
        self._backdrop_img_url = self._img_url
        self._description = info.overview
        self._id = info.id
        self._companies = companies
        self._year = year
        self._runtime = runtime
        self._genres = genres
        self._countries = countries
        self._languages = languages
        self._producers = producers

    def to_post(self):
        """
        View to WP post
        """
        return {
            "title": self._episode_line,
            "movie_first_url": self._link if self._link else self.find_on_storage(),
            "poster_url": self.backdrop_url(),
            "description": self._description,
            "season": [self._season_num],
            "series": [self._series],
            "tvshow_genre": self._genres,
            "tvshow_year": self._year,
            "tvshow_country": self.limit_by(self._countries),
            "tvshow_company": self.limit_by(self._companies),
            "tvshow_language": self.limit_by(self._languages),
            "tvshow_producer": self.limit_by(self._producers),
            "runtime": self._runtime,
            "episode": self._episode_num,
            "tvshow_writer": self.get_from(
                self._crew, lambda x: "Writing" in x.department
            ),
            "tvshow_director": self.get_from(self._crew, lambda x: x.job == "Director"),
            "tvshow_actors": self.get_from(self._cast),
            "img": self.img_url(),
        }

    def fetch_info_from_imdb(self, client):
        """
        Fetching info from IMDb about tv show
        """
        log.info(f"Fetching info from IMDb:{self._episode_line}...")
        show_id = client.search_tv(self._serial_name)[0].movieID
        show = client.get_show_by_id(show_id)
        self._companies = [
            company.data["name"] for company in show.get("production companies")
        ]
        episodes = client.get_show_episodes(show_id)
        episode_id = client.get_episode_id(
            episodes, season_num=self._season_num, episode_num=self._episode_num
        )
        episode = client.get_show_by_id(episode_id)
        self._year = [episode.get("year")]
        self._runtime = (
            int(episode.get("runtimes")[0]) if episode.get(
                "runtimes")[0] else None
        )
        self._genres = episode.get("genres")
        self._countries = episode.get("countries")
        self._languages = episode.get("languages")
        self._producers = [
            producer.get("name") for producer in episode.get("producers")
        ]
        log.info(f"IMDB scraped for:{self._episode_line}")

    def get_from(self, data, predicate=lambda x: x):
        """
        There is simillar structure for dicts,
        so I wrote this function to simply gives info from them

        :type: data: iterable
        :type: predicate: func

        :rtype: list
        """
        if not data:
            return []
        data = [_.name for _ in data if predicate(_) and _.name]
        return self.limit_by(data)

    def limit_by(self, data):
        """
        Safety limits list by self._limit
        """
        #Sometimes some data are not received from IMDB in tv.py 104-107 lines
        if data is None:
            return None
        elif not self._limit or int(self._limit) > len(data):
            return data
        else:
            return data[: int(self._limit)]

    def link(self):
        """
        Returns link of the tv_episode, or trying to find it on storage
        """
        return self._link if self._link else self.find_on_storage()

    def find_on_storage(self):
        """ Trying to find desired movie on the storage using fuzzy search

        Returning url if finds and blank string if not
        :type storage_url: str

        :type desired_movie: str

        :rtype: str
        """
        session = HTMLSession()
        response = session.get(self._storage_url, timeout=10)
        desired_episode = self._episode_line
        episodes = response.html.links
        ratio = fuzz.token_set_ratio
        #TODO: check remove_trash and episodes format. What will be format and whether it's correctly processed in remove_trash
        related_files = [
            (episode, desired_episode, ratio(desired_episode, remove_trash(episode)))
            for episode in episodes
            if ratio(desired_episode, remove_trash(episode)) > 80
        ]
        if related_files:
            best_match = max(
                related_files, key=lambda x: x[2]) if related_files else ""
        else:
            #TODO: incorrect usage of desired_episode. {desired_episode[0]} ({desired_episode[1]}) might be replaced with self._episode_line
            log.info(
                f"There is no {desired_episode[0]} ({desired_episode[1]}) on the {self._storage_url}, I'll leave second_url blank."
            )
            return ""
        return f"{self._storage_url}{best_match[0]}"

    def img_url(self):
        """
            Add prefix to img_url
        """
        return f"https://image.tmdb.org/t/p/w185{self._img_url}"

    def backdrop_url(self):
        """
            Add prefix to backdrop_img_url
        """
        return (
            f"https://image.tmdb.org/t/p/w780{self._backdrop_img_url}"
        )

    def __str__(self):
        return self._episode_line
