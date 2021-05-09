'''
Setting additional loggers. Currently only error_log
'''

import logging

NOT_PROCESSED_FILE = 'logs/errors.log'
# log = logging.getLogger(__name__)
error_log = logging.getLogger('not processed logger')
fh = logging.FileHandler(NOT_PROCESSED_FILE)
fh.setLevel(logging.ERROR)
formatter = logging.Formatter('"%(asctime)s [%(filename)s:%(lineno)s] %(message)s"')
fh.setFormatter(formatter)
error_log.addHandler(fh)