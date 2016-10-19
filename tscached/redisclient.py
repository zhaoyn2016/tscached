from tscached import app
from redis.sentinel import Sentinel
import requests
import simplejson as json


class BackendQueryFailure(requests.exceptions.RequestException):
    """ Raised if the backing TS database (KairosDB) fails. """
    pass


config = app.config['tscached']

def getRedisClient():
    ipaddrs=config['redis']['redis_ipaddrs']
    arr=ipaddrs.split(",")
    arr1=[]
    for s in arr:
        ipaddr=s.split(":")
        t=(ipaddr[0],int(ipaddr[1]))
        arr1.append(t)
    sentinel = Sentinel(arr1, socket_timeout=config['redis']['redis_socket_timeout'], password=config['redis']['redis_password'])
    master_name=config['redis']['redis_master_name']
    sentinel.discover_master(master_name)
    sentinel.discover_slaves(master_name)
    master = sentinel.master_for(master_name, socket_timeout=config['redis']['redis_socket_timeout'])
    return master

def query_kairos(kairos_host, kairos_port, query, propagate=True):
    """ As the name states.
        :param kairos_host: str, host/fqdn of kairos server. commonly a load balancer.
        :param kairos_port: int, port that kairos (or a proxy) listens on.
        :param query: dict to send to kairos.
        :param propagate: bool, should we raise (or swallow) exceptions.
        :return: dict containing kairos' response.
        :raise: BackendQueryFailure if the operation doesn't succeed.
    """
    try:
        url = 'http://%s:%s/api/v1/datapoints/query' % (kairos_host, kairos_port)
        r = requests.post(url, data=json.dumps(query),timeout=config['kairosdb']['kairosdb_timeout'])
        value = json.loads(r.text)
        if r.status_code / 100 != 2:
            message = ', '.join(value.get('errors', ['No message given']))
            if propagate:
                raise BackendQueryFailure('KairosDB responded %d: %s' % (r.status_code, message))
            return {'status_code': r.status_code, 'error': message}
        return value
    except requests.exceptions.RequestException as e:
        if propagate:
            raise BackendQueryFailure('Could not connect to KairosDB: %s' % e.message)
        return {'status_code': 500, 'error': e.message}