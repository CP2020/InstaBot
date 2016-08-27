import asyncio
import itertools
import json
import logging
import re
import urllib.parse
from .errors import ConfigurationError, MediaError
from aiohttp import ClientSession
from aiohttp.errors import ClientResponseError

LOGGER = logging.getLogger('instabot.media_service')
MEDIA_COUNT_MIN = 100


class MediaService:
    def __init__(self, configuration):
        self._hashtags = configuration.hashtags
        if len(self._hashtags) == 0:
            raise ConfigurationError('No hashtags were specified')
        self._media = []
        self._session = ClientSession()

    async def _get_media_by_hashtag(self, hashtag):
        url = 'https://www.instagram.com/explore/tags/{}/'.format(
            urllib.parse.quote(hashtag.encode('utf-8')),
            )
        response = await self._session.get(url)
        response = await response.read()
        response = response.decode('utf-8', errors='ignore')
        match = re.search(
            r'<script type="text/javascript">window\._sharedData = ([^<]+);'
            '</script>',
            response,
            )
        if match is None:
            raise MediaError()
        response = json.loads(match.group(1))
        media = response['entry_data']['TagPage'][0]['tag']['media']['nodes']
        media = [m['id'] for m in media]
        LOGGER.debug(
            '{} media about \"{}\" were fetched'.format(len(media), hashtag),
            )
        return media

    async def run(self):
        for hashtag in itertools.cycle(self._hashtags):
            if len(self._media) < MEDIA_COUNT_MIN:
                try:
                    self._media.extend(
                        (await self._get_media_by_hashtag(hashtag)),
                        )
                except (IOError, OSError, ClientResponseError, MediaError) \
                        as e:
                    LOGGER.warning(e)
                    await asyncio.sleep(5)
                else:
                    await asyncio.sleep(3)
            else:
                await asyncio.sleep(30)

    async def pop(self):
        while True:
            try:
                return self._media.pop(0)
            except IndexError:
                LOGGER.debug('Has no media to pop')
                await asyncio.sleep(5)
