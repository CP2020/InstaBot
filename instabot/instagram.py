import aiohttp
import asyncio
import logging
import json
import re
from .errors import APIError, APIJSONError, APILimitError, APINotAllowedError

BASE_URL = 'https://www.instagram.com/'
LOGGER = logging.getLogger('instabot.instagram')
USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:44.0) Gecko/20100101 Firefox/44.0'

class Client(object):
    def __init__(self, configuration):
        self._client_id = configuration.instagram_client_id
        self._username = configuration.instagram_username
        self._password = configuration.instagram_password
        self._referer = BASE_URL
        self._session = aiohttp.ClientSession(
            cookies={
                'ig_pr': '1',
                'ig_vw': '1280',
                },
            headers={
                'User-Agent': USER_AGENT,
                'X-Instagram-AJAX': '1',
                'X-Requested-With': 'XMLHttpRequest',
                },
            )
        self._anonymous_session = aiohttp.ClientSession(
            headers={
                'User-Agent': USER_AGENT,
                },
            )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._do_login())

    @asyncio.coroutine
    def _ajax(self, url, data=None, referer=None):
        '''
        @raise APIError
        '''
        if referer is not None:
            self._referer = referer
        headers = {
            'Referer': self._referer,
            'X-CSRFToken': self._csrf_token,
            }
        url = BASE_URL + url
        response = yield from self._session.post(
            url,
            data=data,
            headers=headers,
            )
        response = yield from response.text()
        try:
            response = json.loads(response)
        except ValueError as e:
            if 'too many requests' in response:
                raise APILimitError('Too many AJAX requests to {0}'.format(url))
            raise APIError(
                'AJAX request to {0} is not JSON: {1} Response: {2}'.format(url, e, response),
                )
        if response.get('status') != 'ok':
            raise APIError('AJAX request to {0} is not OK: {1}'.format(url, response))
        yield from asyncio.sleep(1.5)
        return response

    @asyncio.coroutine
    def _api(self, path=None, url=None):
        '''
        @raise APIJSONError
        @raise APIError
        '''
        if url is None:
            url = 'https://api.instagram.com/v1/{0}'.format(path)
        response = yield from self._anonymous_session.get(
            url,
            params={
                'client_id': self._client_id,
                },
            )
        response = yield from response.text()
        try:
            response = json.loads(response)
        except ValueError as e:
            raise APIError('Bad response for {0}: {1} Response: {2}'.format(url, e, response))
        self._check_api_response(response)
        yield from asyncio.sleep(1.5)
        return response

    def _check_api_response(self, response):
        '''
        @raise APIJSONError
        '''
        code = response['meta']['code']
        if code == 200:
            return
        message = '{0} ({1}): {2}'.format(
            code,
            response['meta']['error_type'],
            response['meta']['error_message'],
            )
        if code == 400:
            raise APINotAllowedError(message)
        elif code in (403, 429):
            raise APILimitError(message)
        else:
            raise APIJSONError(message)

    @asyncio.coroutine
    def _do_login(self):
        '''
        @raise APIError
        '''
        yield from self._open(BASE_URL)
        self._update_csrf_token()
        yield from self._ajax(
            'accounts/login/ajax/',
            data={
                'username': self._username,
                'password': self._password,
                },
            )
        self._update_csrf_token()
        self.id = self._session.cookies['ds_user_id'].value

    @asyncio.coroutine
    def follow(self, user):
        '''
        @raise APIJSONError
        @raise APIError
        '''
        try:
            yield from self._ajax(
                'web/friendships/{0}/follow/'.format(user),
                referer=user.get_url(),
                )
        except (APIError, APILimitError) as e:
            raise APIError('Troubles during following {0}: {1}'.format(user.instagram_id, e))
        else:
            LOGGER.debug('{0} was followed.'.format(user.username))

    @asyncio.coroutine
    def get_followed(self, user):
        '''
        @raise APIJSONError
        '''
        response = yield from self._api('users/{0}/follows'.format(user.instagram_id))
        followed = response['data']
        next_url = response['pagination'].get('next_url')
        while next_url:
            response = yield from self._api(url=next_url)
            followed.extend(response['data'])
            next_url = response['pagination'].get('next_url')
        LOGGER.debug('%d followed users were fetched.', len(followed))
        return followed

    @asyncio.coroutine
    def get_some_followers(self, user):
        '''
        @raise APIJSONError
        '''
        response = yield from self._api('users/{0}/followed-by'.format(user.instagram_id))
        followers = response['data']
        return followers

    @asyncio.coroutine
    def like(self, media):
        try:
            yield from self._ajax('web/likes/{0}/like/'.format(media))
        except (APIError, APILimitError) as e:
            raise APIError('Troubles during liking {0}: {1}'.format(user.instagram_id, e))
        else:
            LOGGER.debug('Liked {0}'.format(media))

    @asyncio.coroutine
    def _open(self, url):
        headers = {
            'Referer': self._referer,
            }
        response = yield from self._session.get(url, headers=headers)
        self._referer = url
        response = yield from response.text()
        return response

    @asyncio.coroutine
    def unfollow(self, user):
        '''
        @raise APIJSONError
        @raise APIError
        '''
        try:
            response = yield from self._ajax(
                'web/friendships/{0}/unfollow/'.format(user.instagram_id),
                referer=user.get_url(),
                )
        except APILimitError as e:
            raise APILimitError(
                'API limit was reached during unfollowing {0}: {1}'.format(user.username, e),
                )
        except APIError as e:
            raise APIError('API troubles during unfollowing {0}: {1}'.format(user.username, e))
        else:
            LOGGER.debug('{0} was unfollowed.'.format(user.username))

    def _update_csrf_token(self):
        self._csrf_token = self._session.cookies['csrftoken'].value
        LOGGER.debug('API. CSRF token is %s', self._csrf_token)
