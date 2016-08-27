import asyncio
import datetime
import logging
from .errors import APIError, APIJSONError, APILimitError, \
    APINotAllowedError, APINotFoundError
from .stats_service import StatsService
from .user import User
from aiohttp.errors import ClientResponseError

LOGGER = logging.getLogger('instabot.following_service')


class FollowingService:
    def __init__(self, client, configuration):
        self._client = client
        self._following_timedelta = \
            datetime.timedelta(hours=configuration.following_hours)
        self._stats_service = StatsService.get_instance()

    async def run(self):
        while True:
            try:
                await self._unfollow()
                await self._follow()
            except APILimitError as e:
                LOGGER.debug(e)
            except (APIError, APIJSONError) as e:
                LOGGER.debug(e)
                await asyncio.sleep(5)
            except (IOError, OSError, ClientResponseError) as e:
                LOGGER.warning(e)
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(10)

    async def _follow(self):
        '''
        @raise APIError
        @raise APIJSONError
        @raise APILimitError
        '''
        unfollowing_threshold = datetime.datetime.utcnow() - \
            self._following_timedelta
        for user in User.select().where(
                User.was_followed_at == None,
                ).order_by(User.following_depth, User.created):
            try:
                await self._client.follow(user)
            except (APINotAllowedError, APINotFoundError) as e:
                LOGGER.debug('Can\'t follow {}. {}'.format(user.username, e))
                # Make user look like he was followed and was unfollowed
                # already.
                user.is_followed = False
                user.was_followed_at = unfollowing_threshold
            else:
                user.is_followed = True
                user.was_followed_at = datetime.datetime.utcnow()
                self._stats_service.increment('followed')
            user.save()

    async def _unfollow(self):
        '''
        @raise APIError
        @raise APIJSONError
        @raise APILimitError
        '''
        unfollowing_threshold = datetime.datetime.utcnow() - \
            self._following_timedelta
        for user in User.select().where(
                (User.is_followed == True) &
                (User.was_followed_at <= unfollowing_threshold),
                ):
            try:
                await self._client.unfollow(user)
            except (APINotAllowedError, APINotFoundError) as e:
                LOGGER.debug('Can\'t unfollow {}. {}'.format(user.username, e))
            else:
                self._stats_service.increment('unfollowed')
            user.is_followed = False
            user.save()
