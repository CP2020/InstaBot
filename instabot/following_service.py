import asyncio
import datetime
import logging
from .errors import APILimitError
from .user import User

LOGGER = logging.getLogger('instabot')

class FollowingService:
    LONG_AGO_TIMEDELTA = datetime.timedelta(days=5)

    def __init__(self, client):
        self._client = client

    @asyncio.coroutine
    def run(self):
        while True:
            try:
                yield from self._unfollow()
                yield from self._follow()
            except APILimitError as e:
                LOGGER.debug('Instagram limit was reached during following: %s', e)
                yield from asyncio.sleep(60)
            else:
                yield from asyncio.sleep(10)

    @asyncio.coroutine
    def _follow(self):
        for user in User.select().where(User.was_followed_at == None).order_by(
            User.friending_depth.desc(),
            User.friends_fetched.desc(),
            ):
            self._client.follow(user)

    @asyncio.coroutine
    def _unfollow(self):
        long_ago = datetime.datetime.utcnow() - LONG_AGO_TIMEDELTA
        for user in User.select().where((User.is_followed == True) & (User.was_followed_at < long_ago)):
            self._client.unfollow(user)
