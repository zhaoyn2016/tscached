import logging
import socket

from tscached import cache_calls
from tscached import kquery
from tscached.redisclient import BackendQueryFailure

import redis
import redlock


SHADOW_LOCK_KEY = 'tscached:shadow_lock'
SHADOW_SERVER_KEY = 'tscached:shadow_server'
SHADOW_LIST = 'tscached:shadow_list'


def  should_add_to_readahead(config, referrer, headers):
    """ Should we add this KQuery for readahead behavior?
        :param config: dict representing the top-level tscached config
        :param referrer: None or str, from the http request
        :param headers: dict, all headers from the http request
        :return: boolean
    """
    if headers.get(config['shadow']['http_header_name'], None):
        return True

    if not referrer:
        return False

    for substr in config['shadow']['referrer_blacklist']:
        if substr in referrer:
            return False
    return True


def process_for_readahead(config, redis_client, kquery_key, referrer, headers):
    """ Couple this KQuery to readahead behavior. If Redis fails, eat the exception.
        :param config: dict representing the top-level tscached config
        :param redis_client: redis.StrictRedis
        :param kquery_key: str, usually tscached:kquery:HASH
        :param referrer: str, from the http request
        :param headers: dict, all headers from the http request
        :return: void:
        :raise: redis.exceptions.RedisError
    """
    if should_add_to_readahead(config, referrer, headers):
        resp = redis_client.sadd(SHADOW_LIST, kquery_key)
        logging.info('Shadow: Added %d key: %s' % (resp, kquery_key))
    else:
        logging.debug('Shadow: NOT adding key: %s' % kquery_key)


def become_leader(config, redis_client):
    """ tscached can be deployed on multiple servers. Only one of them should exert shadow load.
        We use RedLock (http://redis.io/topics/distlock) to achieve this. If we cannot acquire the
        shadow lock, fail fast. If our server (or this program) crashes, the leader key will expire and
        another server will take over eventually.

        RedLock is (debatably) imperfect, but that's okay with us: our worst case is that some work gets
        done twice -  because we are using Redis as a cache and *not* as a datastore. We're using one of
        the standard Python clientlibs: https://github.com/glasslion/redlock

        This implementation assumes a single-master Redis cluster.

        :param config: dict representing the top-level tscached config
        :param redis_client: redis.StrictRedis
        :return: redlock.RedLock or False
    """
    hostname = socket.gethostname()
    leader_expiration = config['shadow'].get('leader_expiration', 3600) * 1000  # ms expected
    deets = [redis_client]  # no need to reinitialize a redis connection.

    try:
        lock = redlock.RedLock(SHADOW_LOCK_KEY, ttl=leader_expiration, connection_details=deets)
        if lock.acquire():
            # mostly for debugging purposes
            redis_client.set(SHADOW_SERVER_KEY, hostname, px=leader_expiration)
            logging.info('Lock acquired; now held by %s' % hostname)
            return lock
        else:
            other_host = redis_client.get(SHADOW_SERVER_KEY)
            logging.info('Could not acquire lock; lock is held by %s' % other_host)
            return False
    except redis.exceptions.RedisError as e:
        logging.error('RedisError in acquire_leader: ' + e.message)
        return False
    except redlock.RedLockError as e:
        logging.error('RedLockError in acquire_leader: ' + e.message)
        return False


def release_leader(lock, redis_client):
    """ Release the lock acquired in become_leader. If we crash before doing this, no big deal:
        the TTL will save us from doing anything dumb. Still, my mom taught me to clean up after myself.
        :param lock: redlock.RedLock
        :param lock: redis.StrictRedis
        :return: bool, on success/failure
    """
    try:
        lock.release()
        redis_client.delete(SHADOW_SERVER_KEY)
        logging.info('Lock released.')
        return True
    except redis.exceptions.RedisError as e:
        logging.error('RedisError in release_leader: ' + e.message)
        return False
    except redlock.RedLockError as e:
        logging.error('RedLockError in release_leader: ' + e.message)
        return False


def perform_readahead(config, redis_client):
    """ The heart of the readahead script.
        :param config: dict, tscached level of config.
        :param redis_client: redis.StrictRedis
        :return: void
    """
    lock = become_leader(config, redis_client)
    if not lock:
        logging.info('Could not become leader; exiting.')
        return

    try:
        redis_keys = list(redis_client.smembers(SHADOW_LIST))
        logging.info('Found %d KQuery keys in the shadow list' % len(redis_keys))

        for kq in kquery.KQuery.from_cache(redis_keys, redis_client):
            last_ts = kq.cached_data['last_add_data']  # unix timestamp, seconds
            mins_in_past = (last_ts / 60) - 5  # add 5m of margin

            # all that really matters is that end_ values are unset.
            kairos_time_range = {'start_relative': {'unit': 'minutes', 'value': str(mins_in_past)}}
            # throw away the diagnostic mode info for the moment.
            kq_resp, _ = cache_calls.process_cache_hit(config, redis_client, kq, kairos_time_range)
            size = kq_resp.get('sample_size', -1)
            logging.debug('Processed KQuery %s; sample size now at %d' % (kq.redis_key, size))
    except BackendQueryFailure as e:
        logging.error('BackendQueryFailure: %s' % e.message)
    except redis.exceptions.RedisError as e:
        logging.error('RedisError: ' + e.message)

    release_leader(lock, redis_client)
