FROM ubuntu:trusty
MAINTAINER Zach Musgrave <ztm@zachm.us>

RUN apt-get update
RUN apt-get install -y git make
RUN apt-get install -y python2.7 python2.7-dev python-pip
RUN apt-get install -y libyaml-dev libpcre3-dev

ADD . /
RUN chmod +x run-tscached.sh
RUN pip install -Ur requirements.txt
RUN make frontend

CMD ./run-tscached.sh

EXPOSE 8008
