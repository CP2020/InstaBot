import asyncio
import datetime
import logging
from .errors import APIError, APILimitError
from .user import User

LOGGER = logging.getLogger('instabot.following_service')

class FollowingService:
    def __init__(self, client, configuration):
        self._client = client
        self._following_timedelta = datetime.timedelta(hours=configuration.following_hours)

    @asyncio.coroutine
    def run(self):
        while True:
            LOGGER.debug('Cycle')
            try:
                yield from self._unfollow()
                yield from self._follow()
            except APILimitError as e:
                LOGGER.debug(e)
                yield from asyncio.sleep(30)
            except APIError as e:
                LOGGER.debug(e)
                yield from asyncio.sleep(10)
            else:
                yield from asyncio.sleep(10)

    @asyncio.coroutine
    def _follow(self):
        for user in User.select().where(User.was_followed_at == None).order_by(
            User.following_depth,
            User.created,
            ):
            yield from self._client.follow(user)
            user.is_followed = True
            user.was_followed_at = datetime.datetime.utcnow()
            user.save()

    @asyncio.coroutine
    def _unfollow(self):
        unfollowing_threshold = datetime.datetime.utcnow() - self._following_timedelta
        for user in User.select().where(
            (User.is_followed == True) & (User.was_followed_at <= unfollowing_threshold),
            ):
            yield from self._client.unfollow(user)
            user.is_followed = False
            user.save()
