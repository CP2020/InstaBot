import asyncio
import datetime
import logging
import logging.config
import sys
from .configuration import Configuration
from .db import get_db
from .errors import ConfigurationError
from .following_service import FollowingService
from .like_service import LikeService
from .media_service import MediaService
from .stats_service import StatsService
from .user import User
from .user_service import UserService
from docopt import docopt
from instabot import instagram
from os import path

DIR = path.abspath(path.dirname(__file__))
DOC = '''InstaBot

Usage:
  instabot CONFIGURATION
  instabot install CONFIGURATION
  instabot -h | --help | --version

Arguments:
  CONFIGURATION  Path to configuration.yml file.
'''
LOGGER = logging.getLogger('instabot')
__version__ = '0.2.2'

def install(configuration, db):
    db.create_tables([User])
    client = instagram.Client(configuration)
    now = datetime.datetime.utcnow()
    was_followed_at = now - datetime.timedelta(hours=configuration.following_hours)
    user = User.create(
        following_depth=0,
        instagram_id=client.id,
        username=configuration.instagram_username,
        was_followed_at=was_followed_at, # To prevent attempts to follow user by himself.
        )
    loop = asyncio.get_event_loop()
    followed_users_json = loop.run_until_complete(client.get_followed(user))
    for followed_json in followed_users_json:
        User.create(
            following_depth=0,
            instagram_id=followed_json['id'],
            is_followed=True,
            username=followed_json['username'],
            was_followed_at=was_followed_at,
            )
    LOGGER.info('{0} followed users were saved in DB'.format(len(followed_users_json)))

def main():
    arguments = docopt(DOC, version=__version__)
    logging.basicConfig(level=logging.DEBUG)

    configuration = Configuration(arguments['CONFIGURATION'])

    logging.config.dictConfig(configuration.logging)

    db = get_db(configuration)

    if arguments['install']:
        LOGGER.info('Installing InstaBot')
        install(configuration, db)
    else:
        LOGGER.info('Executing InstaBot')
        run(configuration)

def run(configuration):
    loop = asyncio.get_event_loop()

    stats_service = StatsService()
    loop.create_task(stats_service.run())

    following_client = instagram.Client(configuration)

    try:
        user_service = UserService(following_client, configuration)
    except ConfigurationError as e:
        LOGGER.info('UserService wasn\'t started. {}'.format(e))
    else:
        loop.create_task(user_service.run())

    following_service = FollowingService(following_client, configuration)
    loop.create_task(following_service.run())

    try:
        media_service = MediaService(configuration)
    except ConfigurationError as e:
        LOGGER.info('MediaService wasn\'t started. {}'.format(e))
    else:
        loop.create_task(media_service.run())
        like_client = instagram.Client(configuration)
        like_service = LikeService(like_client, media_service)
        loop.create_task(like_service.run())

    loop.run_forever()
