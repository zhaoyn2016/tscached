import logging

from flask import request
import redis
import requests
import simplejson as json

from tscached import app
from tscached.utils import create_key
from tscached.redisclient import getRedisClient

"""
    NOTE: and TODO(?) The big logging block present in handler_general is missing here.
    This module receives it, in normal operation, afaict because it is imported in
    tscached/__init__.py *after* handler_general. This seems janky and should be remediated.
"""


def metadata_caching(config, name, endpoint, post_data=None):
    """ Encapsulate stupid-simple cache logic for Kairos "metadata" endpoints.
        config: nested dict loaded from the 'tscached' section of a yaml file.
        name: string, used as a part of redis keying.
        endpoint: string, the corresponding kairosdb endpoint.
        post_data: None or string. overrides default GET proxy behavior. implies custom keying.
        returns: 2-tuple: (content, HTTP code)
    """
    if post_data:
        redis_key = create_key(post_data, name)
    else:
        redis_key = 'tscached:' + name

    redis_client = getRedisClient()
    try:
        get_result = redis_client.get(redis_key)
    except redis.exceptions.RedisError as e:
        logging.error('RedisError: ' + e.message)
        get_result = False  # proxy through to kairos even if redis is broken

    if get_result:  # hit. no need to process the JSON blob, so don't!
        logging.info('Meta Endpoint HIT: %s' % redis_key)
        return get_result, 200
    else:
        logging.info('Meta Endpoint MISS: %s' % redis_key)
        url = 'http://%s:%s%s' % (config['kairosdb']['kairosdb_host'], config['kairosdb']['kairosdb_port'], endpoint)

        try:
            if post_data:
                kairos_result = requests.post(url, data=post_data)
            else:
                kairos_result = requests.get(url)

        except requests.exceptions.RequestException as e:
            logging.error('BackendQueryFailure: %s' % e.message)
            return json.dumps({'error': 'Could not connect to KairosDB: %s' % e.message}), 500

        if kairos_result.status_code / 100 != 2:
            # propagate the kairos message to the user along with its error code.
            value = json.loads(kairos_result.text)
            value_message = ', '.join(value.get('errors', ['No message given']))
            message = 'Meta Endpoint: %s: KairosDB responded %d: %s' % (redis_key,
                                                                        kairos_result.status_code,
                                                                        value_message)
            return json.dumps({'error': message}), 500
        else:
            # kairos response seems to be okay
            expiry = config['expiry'].get(name, 300)  # 5 minute default

            try:
                set_result = redis_client.set(redis_key, kairos_result.text, ex=expiry)
                if not set_result:
                    logging.error('Meta Endpoint: %s: Cache SET failed: %s' % (redis_key, set_result))
            except redis.exceptions.RedisError as e:
                # Eat the Redis exception - turns these endpoints into straight proxies.
                logging.error('RedisError: ' + e.message)

        return kairos_result.text, kairos_result.status_code, {'Content-Type': 'application/json'}


@app.route('/api/v1/metricnames', methods=['GET'])
def handle_metricnames():
    return metadata_caching(app.config['tscached'], 'metricnames', '/api/v1/metricnames')


@app.route('/api/v1/tagnames', methods=['GET'])
def handle_tagnames():
    return metadata_caching(app.config['tscached'], 'tagnames', '/api/v1/tagnames')


@app.route('/api/v1/tagvalues', methods=['GET'])
def handle_tagvalues():
    return metadata_caching(app.config['tscached'], 'tagvalues', '/api/v1/tagvalues')


@app.route('/api/v1/datapoints/query/tags', methods=['POST'])
def handle_metaquery():
    return metadata_caching(app.config['tscached'], 'metaquery', '/api/v1/datapoints/query/tags',
                            request.data)
