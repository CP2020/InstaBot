import asyncio
import logging
from .errors import APIError, APIJSONError, APILimitError, \
    APINotAllowedError, APINotFoundError
from .stats_service import StatsService
from aiohttp.errors import ClientResponseError

LOGGER = logging.getLogger('instabot.like_service')


class LikeService:
    def __init__(self, client, media_service):
        self._client = client
        self._media_service = media_service
        self._stats_service = StatsService.get_instance()

    @asyncio.coroutine
    def run(self):
        media = yield from self._media_service.pop()
        while True:
            try:
                yield from self._client.like(media)
            except APILimitError as e:
                LOGGER.debug(e)
            except (APIError, APIJSONError) as e:
                LOGGER.debug(e)
                yield from asyncio.sleep(5)
            except (APINotAllowedError, APINotFoundError) as e:
                LOGGER.debug('Can\'t like {}. {}'.format(media, str(e)))
                media = yield from self._media_service.pop()
            except (IOError, OSError, ClientResponseError) as e:
                LOGGER.warning(e)
                yield from asyncio.sleep(5)
            else:
                media = yield from self._media_service.pop()
                self._stats_service.increment('liked')
