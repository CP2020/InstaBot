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

    @asyncio.coroutine
    def _get_media_by_hashtag(self, hashtag):
        url = 'https://www.instagram.com/explore/tags/{}/'.format(
            urllib.parse.quote(hashtag.encode('utf-8')),
            )
        response = yield from self._session.get(url)
        response = yield from response.read()
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

    @asyncio.coroutine
    def run(self):
        for hashtag in itertools.cycle(self._hashtags):
            if len(self._media) < MEDIA_COUNT_MIN:
                try:
                    self._media.extend(
                        (yield from self._get_media_by_hashtag(hashtag)),
                        )
                except (IOError, OSError, ClientResponseError, MediaError) \
                        as e:
                    LOGGER.warning(e)
                    yield from asyncio.sleep(5)
                else:
                    yield from asyncio.sleep(3)
            else:
                yield from asyncio.sleep(30)

    @asyncio.coroutine
    def pop(self):
        while True:
            try:
                return self._media.pop(0)
            except IndexError:
                LOGGER.debug('Has no media to pop')
                yield from asyncio.sleep(5)
