FROM python:3.6
MAINTAINER Pyotr Ermishkin <quasiyoke@gmail.com>

COPY instabot /instabot/
COPY docker-entrypoint.sh /
COPY instabot_runner.py /
COPY requirements.txt /

VOLUME /configuration

RUN pip install -r requirements.txt

CMD ["/docker-entrypoint.sh"]
