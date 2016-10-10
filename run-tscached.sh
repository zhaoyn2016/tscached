#!/usr/bin/env bash

sh -c "sed -i 's/ipaddrs.*/ipaddrs: ${redis_ipaddrs}/' tscached.yaml"
sh -c "sed -i 's/password.*/password: ${redis_password}/' tscached.yaml"
sh -c "sed -i 's/master_name.*/master_name: ${redis_mastername}/' tscached.yaml"
sh -c "sed -i 's/kairosdb_host.*/kairosdb_host: ${kairosdb_host}/' tscached.yaml"
sh -c "sed -i 's/kairosdb_port.*/kairosdb_port: ${kairosdb_port}/' tscached.yaml"
uwsgi --ini tscached.uwsgi.ini --wsgi-file tscached/uwsgi.py