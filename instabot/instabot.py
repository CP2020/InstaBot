import asyncio
import datetime
import logging
import logging.config
import sys
from .configuration import Configuration
from .db import get_db
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
__version__ = '0.2'

def install(client, configuration, db):
    db.create_tables([User])
    now = datetime.datetime.utcnow()
    was_followed_at = now - datetime.timedelta(hours=configuration.following_hours)
    User.create(
        following_depth=0,
        instagram_id=client.id,
        was_followed_at=was_followed_at, # To prevent attempts to follow user by himself.
        )
    loop = asyncio.get_event_loop()
    for followed_id in loop.run_until_complete(client.get_followed(client.id)):
        User.create(
            following_depth=0,
            instagram_id=followed_id,
            is_followed=True,
            was_followed_at=was_followed_at,
            )
    LOGGER.info('Followed users were saved in DB')

def main():
    arguments = docopt(DOC, version=__version__)
    logging.basicConfig(level=logging.DEBUG)

    configuration = Configuration(arguments['CONFIGURATION'])

    logging.config.dictConfig(configuration.logging)

    db = get_db(configuration)
    client = instagram.Client(configuration)

    if arguments['install']:
        LOGGER.info('Installing InstaBot')
        install(client, configuration, db)
    else:
        LOGGER.info('Executing InstaBot')
        run(client, configuration)

def run(client, configuration):
    loop = asyncio.get_event_loop()

    stats_service = StatsService()
    loop.create_task(stats_service.run())

    user_service = UserService(client)
    loop.create_task(user_service.run())
    
    following_service = FollowingService(client)
    loop.create_task(following_service.run())

    media_service = MediaService(configuration)
    loop.create_task(media_service.run())

    like_service = LikeService(client, media_service)
    loop.create_task(like_service.run())
    
    loop.run_forever()
