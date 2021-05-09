"""Translations via Yandex translate"""

import logging
from json import loads

import iso639
import requests

YANDEX_API_KEY = 'trnsl.1.1.20191002T170326Z.f727e49cd61a1a3c.cfc832d2cd5d77048ea3fb01401b37dbbf203206'
YANDEX_BASE_URL = 'https://translate.yandex.net/api/v1.5/tr.json/translate'

log = logging.getLogger(__name__)


def make_translations(cast, crew, target_lang, source_lang ='auto'):
    '''
    translates cast and crew fields. Source language is auto.
    :param cast, crew: data to translate
    :param source_lang: from which language to translate
    :param target_lang: to which language to translate
    :return: nothing. Modifies credits inline
    '''
    if target_lang == 'en' or source_lang == target_lang:
        log.debug('No translation required')
        return
    #if we have not valid 6391 iso codes of languages
    if (source_lang != 'auto' and not iso639.is_valid639_1(source_lang)) or not iso639.is_valid639_1(target_lang):
        raise Exception('Wrong source or target language for translation')
    #Translating cast
    if cast:
        cast_characters = [cast.character for cast in cast]
        cast_names = [cast.name for cast in cast]
        cast_to_translate = [*cast_characters, *cast_names]
        # Source lang is 'auto' by default
        params_cast = {
            'key': YANDEX_API_KEY,
            'text': cast_to_translate,
            'lang': f'{source_lang}-{target_lang}' if source_lang != 'auto' else f'{target_lang}'
        }
        response_cast = requests.post(YANDEX_BASE_URL, params=params_cast)
        if response_cast.status_code != 200:
            log.error('Translation request failed')
            raise Exception("Translation request failed")
        cast_translations = loads(response_cast.text)['text']
        n_cast = len(cast)
        i = 0
        while i < n_cast:
            # we have translations as  character, character, character,.., name, name, name
            # So its length as double of credits.cast
            cast[i].character = cast_translations[i]
            cast[i].name = cast_translations[i + n_cast]
            i += 1
    #Translating crew
    if crew:
        crew_departments = [crew.department for crew in crew]
        crew_jobs = [crew.job for crew in crew]
        crew_names = [crew.name for crew in crew]
        crew_info_to_translate = [*crew_departments, *crew_jobs, *crew_names]
        params_crew = {
            'key': YANDEX_API_KEY,
            'text': crew_info_to_translate,
            'lang': f'{source_lang}-{target_lang}' if source_lang != 'auto' else f'{target_lang}'
        }
        response_crew = requests.post(YANDEX_BASE_URL, params=params_crew)
        if response_crew.status_code != 200:
            log.error('Translation request failed')
            raise Exception(f"Translation request failed")
        crew_translations = loads(response_crew.text)['text']
        n_crew = len(crew)
        i = 0
        while i < n_crew:
            crew[i].department = crew_translations[i]
            crew[i].job = crew_translations[i + n_crew]
            crew[i].name = crew_translations[i + 2 * n_crew]
            i += 1