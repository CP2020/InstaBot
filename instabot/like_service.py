import asyncio
import logging
from .stats_service import StatsService

LOGGER = logging.getLogger('instabot')

class LikeService:
    def __init__(self, client, media_service):
        self._client = client
        self._media_service = media_service
        self._stats_service = StatsService.get_instance()

    @asyncio.coroutine
    def run(self):
        while True:
            media = yield from self._media_service.pop()
            while True:
                try:
                    yield from self._client.like(media)
                except instagram.APIError as e:
                    status_code = int(e.status_code)
                    if status_code in (403, 429):
                        LOGGER.debug('Instagram limits reached during liking: %s', e)
                        yield from asyncio.sleep(60)
                    else:
                        LOGGER.debug('Something went wrong during liking: %s', e)
                        yield from asyncio.sleep(5)
                else:
                    LOGGER.debug('Liked %s', media)
                    self._stats_service.increment('liked')
                    yield from asyncio.sleep(.7)
                    break
