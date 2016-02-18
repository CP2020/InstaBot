import aiohttp
import asyncio
import itertools
import re
import urllib

MEDIA_LENGTH_MIN = 100
WEBSTA_URL = 'http://websta.me/'

class ScheduleError(Exception):
    pass

class MediaService(object):
    def __init__(self, configuration):
        self._hashtags = configuration.hashtags
        self._media = []

    @asyncio.coroutine
    def _get_media_by_hashtag(self, hashtag):
        hashtag_url = '{0}tag/{1}'.format(WEBSTA_URL, urllib.quote(hashtag.encode('utf-8')))
        response = yield from aiohttp.get(hashtag_url)
        return re.findall('span class=\"like_count_([^\"]+)\"', response.text)

    @asyncio.coroutine
    def run(self):
        for hashtag in itertools.cycle(self._hashtags):
            while len(self._media) < MEDIA_LENGTH_MIN:
                self._media.extend((yield from self._get_media_by_hashtag(hashtag)))
            while len(self._media) >= MEDIA_LENGTH_MIN:
                yield from asyncio.sleep(5)

    @asyncio.coroutine
    def pop(self):
        while True:
            try:
                return self._media.pop(0)
            except IndexError:
                yield from asyncio.sleep(1)
