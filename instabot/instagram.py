import aiohttp
import asyncio
import logging
import json
import re
from .errors import APIError, APILimitError, APINotAllowedError

BASE_URL = 'https://www.instagram.com/'
LOGGER = logging.getLogger('instabot')
USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:44.0) Gecko/20100101 Firefox/44.0'

class Client(object):
    def __init__(self, configuration):
        self._client_id = configuration.instagram_client_id
        self._login = configuration.instagram_login
        self._password = configuration.instagram_password
        self._referer = None
        self._session = aiohttp.ClientSession()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._do_login())

    @asyncio.coroutine
    def _ajax(self, url, data=None):
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.7,ru;q=0.3',
            'Connection': 'keep-alive',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'User-Agent': USER_AGENT,
            'X-CSRFToken': self._csrf_token,
            'X-Instagram-AJAX': '1',
            'X-Requested-With': 'XMLHttpRequest',
        }
        if self._referer is not None:
            headers['Referer'] = self._referer
        url = BASE_URL + url
        response = yield from self._session.post(
            url,
            data=data,
            headers=headers,
            )
        response = yield from response.text()
        return response

    @asyncio.coroutine
    def _api(self, path):
        '''
        @raise APIError
        '''
        response = yield from aiohttp.get(
            'https://api.instagram.com/v1/{0}'.format(path),
            params={
                'client_id': self._client_id,
                },
            )
        response = yield from response.json()
        self._check_response(response)
        return response

    def _check_response(self, response):
        '''
        @raise APIError
        '''
        code = response['meta']['code']
        if code == 200:
            return
        elif code == 400:
            raise APINotAllowedError(response)
        elif code in (403, 429):
            raise APILimitError(response)
        else:
            raise APIError(response)

    @asyncio.coroutine
    def _do_login(self):
        yield from self._open(BASE_URL)
        self._update_csrf_token()
        login_response = yield from self._ajax('accounts/login/ajax/', data={
            'username': self._login,
            'password': self._password,
        })
        yield from self._update_id()

    @asyncio.coroutine
    def get_followed(self, user):
        '''
        @raise APIError
        '''
        response = yield from self._api('users/{0}/follows'.format(user))
        followed = self._parse_followed(response)
        next_url = response['pagination'].get('next_url')
        while next_url:
            yield from asyncio.sleep(.7)
            response = yield from aiohttp.get(next_url)
            response = yield from response.json()
            followed.extend(self._parse_followed(response))
            next_url = response['pagination'].get('next_url')
        LOGGER.debug('%d followed users were fetched.', len(followed))
        return followed

    @asyncio.coroutine
    def get_some_followers(self, user):
        '''
        @raise APIError
        '''
        response = yield from self._api('users/{0}/followed-by'.format(user))
        followers = self._parse_followed(response)
        return followers

    @asyncio.coroutine
    def like(self, media):
        yield from self._ajax('web/likes/{0}/like/'.format(media))

    @asyncio.coroutine
    def _open(self, url):
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.7,ru;q=0.3',
            'Connection': 'keep-alive',
            'DNT': '1',
            'User-Agent': USER_AGENT,
        }
        if self._referer is not None:
            headers['Referer'] = self._referer
        response = yield from self._session.get(url)
        self._referer = url
        return (yield from response.text())

    def _parse_followed(self, response):
        try:
            response = response['data']
        except KeyError:
            raise APIError()
        return [follower['id'] for follower in response]

    def _update_csrf_token(self):
        self._csrf_token = self._session.cookies['csrftoken'].value
        LOGGER.debug('API. CSRF token is %s', self._csrf_token)

    @asyncio.coroutine
    def _update_id(self):
        response = yield from self._open(BASE_URL)
        match = re.search(
            '<script\\s+type=\"text/javascript\">\\s*window\\._sharedData\\s*=\\s*' \
                '([^<]*(<(?!/script>)[^<]*)*)\\s*;\\s*</script>',
            response,
            re.DOTALL,
            )
        response = json.loads(match.group(1))
        self.id = response['config']['viewer']['id']
