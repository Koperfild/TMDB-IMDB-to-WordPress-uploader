import time
from threading import Lock
import requests
import logging

#TODO: put somewhere for general purposes of all modules
API_KEY = "9ef710d4561ef740d1e11316dd5f94c5"
lock = Lock()
RATE_LIMIT = 38
_remaining_requests = RATE_LIMIT

TOTAL_CALLS = 0
log = logging.getLogger(__name__)

def synchronize_TMDB():
    with lock:
        global TOTAL_CALLS
        TOTAL_CALLS += 1
        global _remaining_requests
        # log.info(_remaining_requests)
        if _remaining_requests <= 5:
            # TOTAL_CALLS += 1
            response = requests.get(
                f"https://api.themoviedb.org/3/movie/420818?api_key={API_KEY}&language=en-US")
            if response.status_code == 200:
                _remaining_requests = max(_remaining_requests, int(response.headers._store['x-ratelimit-remaining'][1]))
                # log.info(f"{_remaining_requests} :response remaining")
            elif response.status_code == 429 and response.reason == 'Too Many Requests':
                retry_after = int(response.headers._store['retry-after'][1])
                time.sleep(retry_after + 200.5)
                _remaining_requests = RATE_LIMIT
            else:
                raise Exception('Error in synchronization')
        else:
            _remaining_requests -= 1
