"""Adds all processed movies/shows/etc to csv files which represent databases. Every time fetch_movies.py or fetch_tv.py
is run this file is updated"""

import logging
import threading

import pandas as pd
from natsort import natsorted, ns
import sys

from helpers import parse_episodes, Episode
from movie import WPMovie, Movie
from tv import TVEpisode

TV_SHOWS_CSV_PATH = 'tvs.csv'
#index in csv file. Need for any sought entity. As every csv file firstly transforms so that as columns it has only wp urls
#and as row index some UID for each entity to distinguish them
TV_INDEX = 'tv_show'
MOVIES_CSV_PATH = 'movies.csv'
MOVIES_INDEX = ['movie','year']
#mapping entity attributes to index: tuple even if there is only 1 attr. Order is important_
entity2index_attrs = {Episode: '_episode_line', TVEpisode: '_episode_line', WPMovie: ('title', 'year'), Movie: ('_movie_name', 'movie_year')}

def get_obj_index_val(obj):
    '''
    Makes tuple representing index entrance for obj entity
    :param obj:
    :return:
    '''
    try:
        attr_names = entity2index_attrs[type(obj)]
        if isinstance(attr_names, tuple):
            return tuple(getattr(obj, attr).lower() if isinstance(getattr(obj, attr), str) else getattr(obj,attr) for attr in attr_names)
        #case of just 'string' as Index
        else:
            return getattr(obj, attr_names)
    except Exception as e:
        log.info('jjj')

def get_obj_index_vals(objs):
    '''
    Extracts index tuples from objects for dataframe lookup and other operations
    :param objs:
    :return: list of tuples representing index lookup for passed objs
    '''
    if not objs:
        return []
    attr_names = entity2index_attrs[type(objs[0])]
    if isinstance(attr_names, tuple):
        return [tuple(getattr(obj, attr) for attr in attr_names) for obj in objs]
    else:
        return [getattr(obj, attr_names) for obj in objs]

log = logging.getLogger(__name__)

#TODO remake to functions out of class
class DataBaseManager:
    _df_initial = None
    _lock = threading.Lock()

    @staticmethod
    def _add_processed_objs(df, objs, wp_url):
        '''
        Adds episodes to _df_modified dataframe to save then in csv file (method write_to_csv())
        :param objs:
        :param wp_url: single url or iterable of urls
        :return:
        '''
        objs_index_tuples = get_obj_index_vals(objs)
        new_index = natsorted(df.index.append(pd.Index(objs_index_tuples)).drop_duplicates())
        df = df.reindex(index=new_index, fill_value=False)
        df.loc[objs_index_tuples, wp_url] = True
        return df
        

    @staticmethod
    def write_movies_to_csv(wp2posted_movies, index_cols=MOVIES_INDEX, csv_path=MOVIES_CSV_PATH):
        DataBaseManager._write_to_csv(wp2posted_movies, index_cols, csv_path)

    @staticmethod
    def write_episodes_to_csv(wp2posted_eps, index_cols=TV_INDEX, csv_path=TV_SHOWS_CSV_PATH):
        DataBaseManager._write_to_csv(wp2posted_eps, index_cols, csv_path)

    @staticmethod
    def _write_to_csv(wp2posted_entities, index_cols, csv_path):
        '''
        Adds posted movies/episodes to database file - csv_path
        :param wp2posted_entities:
        :param index_cols:
        :param csv_path:
        :return:
        '''
        DataBaseManager._df_initial = DataBaseManager._get_df(index_cols, csv_path)
        for wp, objs in wp2posted_entities.items():
            DataBaseManager._df_initial = DataBaseManager._add_processed_objs(DataBaseManager._df_initial, objs, wp.url)
        with DataBaseManager._lock:
            # if new row or column were inserted we set newly created empty cells (filled with NaN) with False
            #might be deleted as logic of filling empty cells is implemented in add_processed_episodes
            DataBaseManager._df_initial.fillna(value=False)
            while True:
                try:
                    DataBaseManager._df_initial.to_csv(csv_path, na_rep=False, index_label=index_cols)
                    log.info(f"Uploaded episodes successfully saved to {csv_path}")
                    break
                except IOError as e:
                    log.error(str(e))
                    log.error("I/O error({0}): {1}".format(e.errno, e.strerror))
                    inp = input("If you want to retry save uploaded episodes to 'tvs.csv' close it if it's used and input Y or y. If you don't want to retry input anything else\n")
                    inp = inp.lower()
                    if inp.lower() != 'y':
                        break
                except:  # handle other exceptions such as attribute errors
                    log.error("Unexpected error saving tvs.csv:", sys.exc_info()[0])
                    break

    @staticmethod
    def _get_df(index_columns, csv_path):
        '''

        :param index_columns: list or single value. Columns by which will be set_index
        :param csv_path:
        :return:
        '''
        if DataBaseManager._df_initial is None:
            df = pd.read_csv(csv_path)
            # TODO: if there is 2 rows with identical tv_show raise Exception
            df.drop_duplicates(inplace=True)
            df = df.set_index(index_columns)
            DataBaseManager._df_initial = df
        return DataBaseManager._df_initial


    @staticmethod
    def get_movies_to_upload(movies, wp_clients, index_cols=MOVIES_INDEX, csv_path=MOVIES_CSV_PATH):
        return DataBaseManager.get_objs_to_upload(movies, wp_clients, index_cols, csv_path)

    @staticmethod
    def get_episodes_to_upload(episodes, wp_clients, index_cols=TV_INDEX, csv_path=TV_SHOWS_CSV_PATH):
        return DataBaseManager.get_objs_to_upload(episodes, wp_clients, index_cols, csv_path)

    @staticmethod
    def get_objs_to_upload(objs, wp_clients, index_cols, csv_path):
        '''
        Checks whether provided episodes are on wp_clients. Info is taken from csv file with columns ["Episode", "WP1","WP2",..], rows are
        like: ["Game of thrones Season 3 Episode 2", True, False,..] where True means WP1 contains this episode
        :param objs: episodes/movies from some storage. Must be contained in db.entity2index_val which attrs correspond to index in its csv file
        :param wp_clients: wp to where episodes must be uploaded
        :param index_cols: columns by which will be set_index
        :return: episodes which are not at least at any of wp_clients
        '''
        df = DataBaseManager._get_df(index_cols, csv_path)
        wp_urls_to_upload_to = {wp_client.url for wp_client in wp_clients}
        #delete placed inside self._get_df()
        #df = df.set_index(['tv_show'])
        if wp_urls_to_upload_to - set(df.columns):
            episodes_to_upload = objs
        #case when wp_clients <= wp urls (df columns)
        else:
            #episodes which are not written to db (by comparing index with obj index representation)
            lowered_df_index = lower_index(df.index)
            episodes_to_upload = [obj for obj in objs if get_obj_index_val(obj) not in lowered_df_index]
            #narrow columns to only sought (search) wps
            df = df[wp_urls_to_upload_to]
            # exclude tv_shows which are uploaded to all desired urls
            df2 = df[~df.all(axis=1)]
            #this is what we also need to upload
            lowered_df2_index = lower_index(df2.index)
            episodes_to_upload.extend([obj for obj in objs if get_obj_index_val(obj) in lowered_df2_index])
        return episodes_to_upload

def lower_index(df_index):
    '''
    Creates new index out of df_index with lowered strings
    :param df_index:
    :return:
    '''
    lowered_df_index = []
    for obj in df_index:
        if isinstance(obj, tuple):
            lowered_df_index.append(tuple(x.lower() if isinstance(x, str) else x for x in obj))
        elif isinstance(obj, str):
            lowered_df_index.append(obj.lower())
        else:
            lowered_df_index.append(obj)
    return lowered_df_index

def log_filtered_objs(all_objs, objs_to_upload):
    '''
    Outputs to logger which episodes must be uploaded and which must not
    Requires str implementation for objs for more appropriate look
    :param all_objs: all episodes which were asked to upload to wps
    :param objs_to_upload: subset of all_episodes
    '''
    if not objs_to_upload:
        log.info("All wps already have provided episodes")
    log.info(f"{'Episode':70s} Already on all wp sites")
    objs_to_log = natsorted(all_objs, key=lambda x: get_obj_index_val(x), alg=ns.IGNORECASE)
    [log.info(f"{str(obj):70s} -") if obj in objs_to_upload else log.info(f"{str(obj):70s} +") for obj in objs_to_log]