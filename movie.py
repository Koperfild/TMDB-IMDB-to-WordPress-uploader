"""Movie class to request, store, and process (translate and so on) movie info. """

import iso639
from fuzzywuzzy import fuzz
from requests_html import HTMLSession

from helpers import json_to_obj
import logging

from translate import make_translations


APPS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbz9rKl08Ot03qn_ZtVFsCJNZTF4-dGfucTAgdBB1eAJdNRATD2m/exec'

def remove_trash(url, movie):
    """
    Removing dots, and other trash from movie url
    """
    url = url.replace(".", " ")
    url_slice = url[: len(movie)] if movie[1] else url[: len(movie) - 4]
    return url_slice


class Movie:
    def __init__(self, movie, storage_url, movie_name, link=None, limit=None, language=None):
        '''
        Initializes movie. Makes requests for info, credits with passed language. Additional translation of non translated
        fields by TMDB is made.
        :param language: If not provided None means no translations
        '''
        response = movie.info(language=language, append_to_response='credits,release_dates')
        info = json_to_obj(response)
        credits = json_to_obj(response['credits'])
        log = logging.getLogger(__name__)
        if language is not None:
            log.info(f'Translating:{movie_name}')
            #Additional translation of some fields. modifies cast and crew
            make_translations(credits.cast, credits.crew, target_lang=language, source_lang='auto')
            log.info(f'Translated:{movie_name}')
        self._release_dates = json_to_obj(response['release_dates'])

        self._link = link
        self._limit = limit
        self._storage_url = storage_url
        self._movie_name = movie_name if movie_name is not None else info.title
        self._title = info.title
        self._cast = credits.cast
        self._crew = credits.crew
        self._img_url = info.poster_path
        self._backdrop_img_url = info.backdrop_path
        self._description = info.overview
        self._companies = info.production_companies
        self._countries = info.production_countries
        # self._languages = info.spoken_languages
        self._languages = [info.original_language]
        # print(self._languages)
        self._id = info.id
        self._runtime = info.runtime
        self._homepage = info.homepage
        self._release_date = info.release_date
        self._movie_year = [int(self._release_date.split("-")[0])]
        #added for db.py support of extracting to search in csv
        self.movie_year = self._movie_year[0]
        self._genres = info.genres

    def __str__(self):
        return f"""
title: {self._title},
description: {self._description},
movie_first_url: {self.find_on_storage()},
poster_url: {self.backdrop_url()},
runtime: {self._runtime},
writers: {self.get_from(self._crew, lambda x: "Writing" in x.department)},
mpaaratings:ke {self.mpaa()},
language: {iso639.to_name(self._languages[0])},
company: {self.get_from(self._companies)},
producer: {self.get_from(self._crew, lambda x: "Production" in x.department)},
director: {self.get_from(self._crew, lambda x: x.job == "Director")},
country: {self.get_from(self._countries)},
genres: {self.get_from(self._genres)},
movie_year: {self._movie_year},
actors: {self.get_from(self._cast)},
mpaa: {self.mpaa()},
img: {self.img_url()},
"""

    def to_post(self):
        """
        Represents a view for WP
        """
        language = iso639.to_name(self._languages[0])
        # print(f"Original language: {language}")
        language = language if ";" not in language else language.split(";")[0]
        return {
            "title": self._title,
            "description": self._description,
            "movie_first_url": self._link if self._link else self.find_on_storage(),
            "poster_url": self.backdrop_url(),
            "runtime": self._runtime,
            "writer": self.get_from(self._crew, lambda x: "Writing" in x.department),
            "mpaaratings": self.mpaa(),
            "language": [language],
            "company": self.get_from(self._companies),
            "producer": self.get_from(
                self._crew, lambda x: "Production" in x.department
            ),
            "director": self.get_from(self._crew, lambda x: x.job == "Director"),
            "country": self.get_from(self._countries),
            "movie_genre": self.get_from(self._genres),
            "movie_year": self._movie_year,
            "actors": self.get_from(self._cast),
            "mpaa": self.mpaa(),
            "img": self.img_url(),
        }

    def convert_iso639_to_lang(self, data):
        if not data:
            return []
        data = [iso639.to_name(_.iso_639_1) for _ in data]
        return data

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
        if not self._limit or int(self._limit) > len(data):
            return data
        else:
            return data[: int(self._limit)]

    def link(self):
        """
        Returns link on video if it setted, else try to find it on storage

        rtype: str
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
        desired_movie = self._movie_name
        movies = response.html.links
        ratio = fuzz.token_set_ratio
        related_files = [
            (
                movie,
                desired_movie,
                ratio(desired_movie, remove_trash(movie, desired_movie)),
            )
            for movie in movies
            if ratio(desired_movie, remove_trash(movie, desired_movie)) > 80
        ]
        if related_files:
            best_match = max(
                related_files, key=lambda x: x[2]) if related_files else ""
        else:
            print(
                f"There is no {desired_movie[0]} ({desired_movie[1]}) on the {self._storage_url}, I'll leave second_url blank."
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

    def mpaa(self):
        """
            Inspect mpaa ratings from response
        """
        mpaa = [
            _.release_dates[0].certification
            for _ in self._release_dates.results
            if _.iso_3166_1 == "US"
        ]
        return list(filter(None, mpaa))


class WPMovie:
    def __init__(self, title, year, link):
        self.title = title
        self.year = int(year)
        self.link = link

    def __str__(self):
        return f"{self.title} {self.year}"