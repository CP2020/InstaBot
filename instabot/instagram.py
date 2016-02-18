import aiohttp
import asyncio
import logging
from .errors import APIError, APILimitError

API_URL = 'https://api.instagram.com/v1/'
BASE_URL = 'https://www.instagram.com/'
LOGGER = logging.getLogger('instabot')

class Client(object):
    def __init__(self, configuration):
        self._client_id = configuration.instagram_client_id
        #self._cookiejar = mechanize.CookieJar()
        #self._browser = mechanize.Browser()
        #self._browser.set_cookiejar(self._cookiejar)
        self._login = configuration.instagram_login
        self._password = configuration.instagram_password
        self._session = aiohttp.ClientSession()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._do_login())

    @asyncio.coroutine
    def _ajax(self, url, params=None, referer=None):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:43.0) Gecko/20100101 Firefox/43.0',
            'X-CSRFToken': self._csrf_token,
            'X-Instagram-AJAX': '1',
            'X-Requested-With': 'XMLHttpRequest',
        }
        if referer is not None:
            headers['Referer'] = referer
        try:
            response = yield from self._session.get(
                BASE_URL + url,
                params=params,
                headers=headers,
                )
            response = yield from response.json()
        except Exception as e:
            raise self._build_error(e)
        return response

    def _build_error(self, e):
        if e.getcode() in (403, 429):
            return APILimitError()
        else:
            return APIError(e)

    @asyncio.coroutine
    def get_followers(self, user):
        response = yield from self._get_followers(user=user)
        for follower in self._parse_followers(response):
            yield follower
        next_url = response['pagination'].get('next_url')
        while next_url:
            yield from asyncio.sleep(.7)
            response = yield from self._get_followers(url=next_url)
            for follower in self._parse_followers(response):
                yield follower
            next_url = response['pagination'].get('next_url')

    @asyncio.coroutine
    def get_some_followers(self, user):
        response = yield from self._get_followers(user)
        return self._parse_followers(response)

    @asyncio.coroutine
    def _get_followers(self, user=None, url=None):
        if url is None:
            url = '{0}users/{1}/followed-by?client_id={2}'.format(API_URL, user, self._client_id)
        response = yield from aiohttp.get(url)
        response = yield from response.json()
        return response

    @asyncio.coroutine
    def _open(self, url):
        response = yield from self._session.get(url)
        yield from response.text()

    def _parse_followers(self, response):
        return [follower['id'] for follower in response['params']]

    @asyncio.coroutine
    def like(self, media):
        yield from self._ajax('web/likes/%s/like/' % media, params='')

    @asyncio.coroutine
    def _do_login(self):
        login_page_url = BASE_URL
        response = yield from self._open(login_page_url)
        self._update_csrf_token()
        login_response = yield from self._ajax('accounts/login/ajax/', referer=login_page_url, params={
            'username': self._login,
            'password': self._password,
        })

    def _update_csrf_token(self):
        self._csrf_token = self._session.cookies['csrftoken'].value
        LOGGER.debug('API. CSRF token is %s', self._csrf_token)
