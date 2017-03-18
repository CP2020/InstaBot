import asyncio
import itertools
import logging
from .errors import APIError, ConfigurationError
from aiohttp.errors import ClientResponseError

LOGGER = logging.getLogger('instabot.media_service')
MEDIA_COUNT_MIN = 100


class MediaService:
    def __init__(self, client, configuration):
        self._hashtags = configuration.hashtags
        if len(self._hashtags) == 0:
            raise ConfigurationError('No hashtags were specified')
        self._media = []
        self._client = client

    async def run(self):
        for hashtag in itertools.cycle(self._hashtags):
            try:
                media = await self._client.get_media_by_hashtag(hashtag)
            except (APIError, ClientResponseError, IOError, OSError) as e:
                LOGGER.warning(e)
                await asyncio.sleep(5)
            else:
                self._media.extend(media)
                await asyncio.sleep(3)
            while len(self._media) >= MEDIA_COUNT_MIN:
                await asyncio.sleep(30)

    async def pop(self):
        while True:
            try:
                return self._media.pop(0)
            except IndexError:
                LOGGER.debug('Has no media to pop')
                await asyncio.sleep(5)
