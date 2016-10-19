#!/usr/bin/env bash

sh -c "sed -i 's/redis_ipaddrs.*/redis_ipaddrs: ${redis_ipaddrs}/' tscached.yaml"
sh -c "sed -i 's/redis_socket_timeout.*/redis_socket_timeout: ${redis_timeout}/' tscached.yaml"
sh -c "sed -i 's/redis_password.*/redis_password: ${redis_password}/' tscached.yaml"
sh -c "sed -i 's/redis_master_name.*/redis_master_name: ${redis_mastername}/' tscached.yaml"
sh -c "sed -i 's/kairosdb_host.*/kairosdb_host: ${kairosdb_host}/' tscached.yaml"
sh -c "sed -i 's/kairosdb_port.*/kairosdb_port: ${kairosdb_port}/' tscached.yaml"
sh -c "sed -i 's/kairosdb_timeout.*/kairosdb_timeout: ${kairosdb_timeout}/' tscached.yaml"

uwsgi --ini tscached.uwsgi.ini --wsgi-file tscached/uwsgi.py