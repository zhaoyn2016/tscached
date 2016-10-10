from tscached import app
from redis.sentinel import Sentinel


def getRedisClient():
    config = app.config['tscached']
    ipaddrs=config['redis']['ipaddrs']
    arr=ipaddrs.split(",")
    arr1=[]
    for s in arr:
        ipaddr=s.split(":")
        t=(ipaddr[0],int(ipaddr[1]))
        arr1.append(t)
    sentinel = Sentinel(arr1, socket_timeout=config['redis']['socket_timeout'], password=config['redis']['password'])
    master_name=config['redis']['master_name']
    sentinel.discover_master(master_name)
    sentinel.discover_slaves(master_name)
    master = sentinel.master_for(master_name, socket_timeout=config['redis']['socket_timeout'])
    return master

