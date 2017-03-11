import asyncio
import datetime
import logging
import logging.config
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
  instabot unfollow CONFIGURATION
  instabot -h | --help | --version

Arguments:
  CONFIGURATION  Path to configuration.yml file.
'''
LOGGER = logging.getLogger('instabot')
__version__ = '0.3.3'


def install(configuration, db):
    LOGGER.info('Installing InstaBot')
    db.create_tables([User])
    client = instagram.Client(configuration)
    now = datetime.datetime.utcnow()
    was_followed_at = now - \
        datetime.timedelta(hours=configuration.following_hours)
    user = User.create(
        following_depth=0,
        instagram_id=client.id,
        username=configuration.instagram_username,
        # To prevent attempts to follow user by himself.
        was_followed_at=was_followed_at,
        )

    unfollow(configuration)


def main():
    arguments = docopt(DOC, version=__version__)
    logging.basicConfig(level=logging.DEBUG)

    configuration = Configuration(arguments['CONFIGURATION'])

    logging.config.dictConfig(configuration.logging)

    db = get_db(configuration)

    if arguments['install']:
        install(configuration, db)
    elif arguments['unfollow']:
        unfollow(configuration)
    else:
        run(configuration)


def run(configuration):
    LOGGER.info('Executing InstaBot')
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


def unfollow(configuration):
    LOGGER.info('Scheduling unfollowing of everyone')
    client = instagram.Client(configuration)
    loop = asyncio.get_event_loop()
    followed_users_json = loop.run_until_complete(client.get_followed(
        User.get(instagram_id=client.id),
        ))
    now = datetime.datetime.utcnow()
    was_followed_at = now - \
        datetime.timedelta(hours=configuration.following_hours)
    for followed_json in followed_users_json:
        try:
            user = User.get(instagram_id=followed_json['id'])
        except User.DoesNotExist:
            user = User(instagram_id=followed_json['id'])
        user.username = followed_json['username']
        user.following_depth = 0
        user.is_followed = True
        if not user.was_followed_at or was_followed_at < user.was_followed_at:
            user.was_followed_at = was_followed_at
        user.save()
    LOGGER.info(
        '{0} followed users were saved in DB'.format(len(followed_users_json)),
        )
