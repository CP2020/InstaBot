import asyncio
import itertools
import logging
import re
import urllib.parse
from .errors import ConfigurationError
from aiohttp import ClientSession

LOGGER = logging.getLogger('instabot.media_service')
MEDIA_COUNT_MIN = 100
WEBSTA_URL = 'http://websta.me/'

class ScheduleError(Exception):
    pass

class MediaService(object):
    def __init__(self, configuration):
        self._hashtags = configuration.hashtags
        if len(self._hashtags) == 0:
            raise ConfigurationError('No hashtags were specified')
        self._media = []
        self._session = ClientSession()

    @asyncio.coroutine
    def _get_media_by_hashtag(self, hashtag):
        url = '{}tag/{}'.format(WEBSTA_URL, urllib.parse.quote(hashtag.encode('utf-8')))
        response = yield from self._session.get(url)
        response = yield from response.read()
        response = response.decode('utf-8', errors='ignore')
        media = re.findall('span class=\"like_count_([^\"]+)\"', response)
        LOGGER.debug('{} media about \"{}\" were fetched'.format(len(media), hashtag))
        return media

    @asyncio.coroutine
    def run(self):
        for hashtag in itertools.cycle(self._hashtags):
            if len(self._media) < MEDIA_COUNT_MIN:
                try:
                    self._media.extend((yield from self._get_media_by_hashtag(hashtag)))
                except (IOError, OSError) as e:
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
