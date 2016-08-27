import asyncio
import logging
import json
from .errors import APIError, APIJSONError, APILimitError, \
    APINotAllowedError, APINotFoundError
from aiohttp import ClientSession

BASE_URL = 'https://www.instagram.com/'
LOGGER = logging.getLogger('instabot.instagram')
USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:46.0) ' \
    'Gecko/20100101 Firefox/46.0'


class Client(object):
    def __init__(self, configuration):
        self._client_id = configuration.instagram_client_id
        self._limit_sleep_time_coefficient = configuration
        .instagram_limit_sleep_time_coefficient
        self._limit_sleep_time_min = configuration
        .instagram_limit_sleep_time_min
        self._success_sleep_time_coefficient = configuration
        .instagram_success_sleep_time_coefficient
        self._success_sleep_time_max = configuration
        .instagram_success_sleep_time_max
        self._success_sleep_time_min = configuration
        .instagram_success_sleep_time_min
        self._limit_sleep_time = self._limit_sleep_time_min
        self._success_sleep_time = self._success_sleep_time_max
        self._username = configuration.instagram_username
        self._password = configuration.instagram_password
        self._referer = BASE_URL
        self._session = ClientSession(
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
        self._anonymous_session = ClientSession(
            headers={
                'User-Agent': USER_AGENT,
                },
            )
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._do_login())

    async def _ajax(self, url, data=None, referer=None):
        '''
        @raise APIError
        @raise APIJSONError
        @raise APILimitError
        @raise APINotAllowedError
        @raise APINotFoundError
        '''
        if referer is not None:
            self._referer = referer
        headers = {
            'Referer': self._referer,
            'X-CSRFToken': self._csrf_token,
            }
        url = BASE_URL + url
        response = await self._session.post(
            url,
            data=data,
            headers=headers,
            )
        if response.status == 404:
            response.close()
            await self._sleep_success()
            raise APINotFoundError(
                'AJAX response status code is 404 for {}'.format(url),
                )
        elif 500 <= response.status < 600:
            response.close()
            await self._sleep_success()
            raise APIError(response.status)
        text = await response.text()
        try:
            response_json = json.loads(text)
        except ValueError as e:
            if 'too many requests' in text or 'temporarily blocked' in text:
                await self._sleep_limit()
                raise APILimitError(
                    'Too many AJAX requests. URL: {}'.format(url),
                    )
            message = 'AJAX request to {url} is not JSON: {error} ' \
                'Response ({status}): \"{text}\"'.format(
                    url=url,
                    error=e,
                    status=response.status,
                    text=text,
                    response=response,
                    ),
            if response.status == 200:
                await self._sleep_success()
                raise APIError(message)
            elif response.status == 400:
                await self._sleep_success()
                raise APINotAllowedError(message)
            else:
                await self._sleep_success()
                raise APIError(message)
        if response_json.get('status') != 'ok':
            raise APIError(
                'AJAX request to {} is not OK: {}'.format(url, response_json),
                )
        await self._sleep_success()
        return response_json

    async def _api(self, path=None, url=None):
        '''
        @raise APIJSONError
        @raise APILimitError
        @raise APINotAllowedError
        @raise APIError
        '''
        if url is None:
            url = 'https://api.instagram.com/v1/{}'.format(path)
        response = await self._anonymous_session.get(
            url,
            params={
                'client_id': self._client_id,
                },
            )
        response = await response.text()
        try:
            response = json.loads(response)
        except ValueError as e:
            raise APIError(
                'Bad response for {}: {} Response: {}'
                .format(url, e, response),
                )
        await self._check_api_response(response)
        await self._sleep_success()
        return response

    async def _check_api_response(self, response):
        '''
        @raise APIJSONError
        @raise APILimitError
        @raise APINotAllowedError
        '''
        code = response['meta']['code']
        if code == 200:
            return
        message = '{code} ({type}): {message}'.format(
            code=code,
            type=response['meta']['error_type'],
            message=response['meta']['error_message'],
            )
        if code == 400:
            raise APINotAllowedError(message)
        elif code in (403, 429):
            await self._sleep_limit()
            raise APILimitError(message)
        else:
            raise APIJSONError(message)

    async def _do_login(self):
        '''
        @raise APIJSONError
        @raise APILimitError
        @raise APINotAllowedError
        @raise APIError
        '''
        await self._open(BASE_URL)
        self._update_csrf_token()
        await self._ajax(
            'accounts/login/ajax/',
            data={
                'username': self._username,
                'password': self._password,
                },
            )
        self._update_csrf_token()
        self.id = self._session.cookies['ds_user_id'].value

    async def follow(self, user):
        '''
        @raise APIJSONError
        @raise APILimitError
        @raise APINotAllowedError
        @raise APINotFoundError
        @raise APIError
        '''
        try:
            await self._ajax(
                'web/friendships/{}/follow/'.format(user.instagram_id),
                referer=user.get_url(),
                )
        except APILimitError as e:
            raise APILimitError(
                'API limit was reached during following {}. {}'
                .format(user.username, e),
                )
        except APIError as e:
            raise APIError(
                'API troubles during following {}. {}'
                .format(user.username, e),
                )
        else:
            LOGGER.debug('{} was followed'.format(user.username))

    async def get_followed(self, user):
        '''
        @raise APIJSONError
        @raise APILimitError
        @raise APINotAllowedError
        @raise APIError
        '''
        response = await self._api(
            'users/{}/follows'.format(user.instagram_id),
            )
        followed = response['data']
        next_url = response['pagination'].get('next_url')
        while next_url:
            response = await self._api(url=next_url)
            followed.extend(response['data'])
            next_url = response['pagination'].get('next_url')
        LOGGER.debug('{} followed users were fetched'.format(len(followed)))
        return followed

    async def get_some_followers(self, user):
        '''
        @raise APIJSONError
        @raise APILimitError
        @raise APINotAllowedError
        @raise APIError
        '''
        response = await self._api(
            'users/{}/followed-by'.format(user.instagram_id),
            )
        followers = response['data']
        return followers

    async def like(self, media):
        '''
        @raise APIError
        @raise APIJSONError
        @raise APILimitError
        @raise APINotAllowedError
        @raise APINotFoundError
        '''
        try:
            await self._ajax('web/likes/{}/like/'.format(media))
        except APILimitError as e:
            raise APILimitError(
                'API limit was reached during liking {}. {}'.format(media, e),
                )
        else:
            LOGGER.debug('Liked {}'.format(media))

    async def _open(self, url):
        headers = {
            'Referer': self._referer,
            }
        response = await self._session.get(url, headers=headers)
        self._referer = url
        response = await response.text()
        return response

    async def relogin(self):
        await self._session.close()
        self._session.cookies.clear()
        await self._do_login()

    async def _sleep_limit(self):
        LOGGER.debug(
            'Sleeping for {:.0f} sec because of API limits'
            .format(self._limit_sleep_time),
            )
        await asyncio.sleep(self._limit_sleep_time)
        self._limit_sleep_time *= self._limit_sleep_time_coefficient

    async def _sleep_success(self):
        if self._limit_sleep_time != self._limit_sleep_time_min:
            self._limit_sleep_time = self._limit_sleep_time_min
            self._success_sleep_time = self._success_sleep_time_max
        await asyncio.sleep(self._success_sleep_time)
        self._success_sleep_time = self._success_sleep_time_min + \
            (self._success_sleep_time - self._success_sleep_time_min) * \
            self._success_sleep_time_coefficient

    async def unfollow(self, user):
        '''
        @raise APIError
        @raise APIJSONError
        @raise APILimitError
        @raise APINotAllowedError
        @raise APINotFoundError
        '''
        try:
            response = await self._ajax(
                'web/friendships/{}/unfollow/'.format(user.instagram_id),
                referer=user.get_url(),
                )
        except APILimitError as e:
            raise APILimitError(
                'API limit was reached during unfollowing {}. {}'
                .format(user.username, e),
                )
        except APIError as e:
            raise APIError(
                'API troubles during unfollowing {}. {}'
                .format(user.username, e),
                )
        else:
            LOGGER.debug('{} was unfollowed'.format(user.username))

    def _update_csrf_token(self):
        self._csrf_token = self._session.cookies['csrftoken'].value
        LOGGER.debug('CSRF token is %s', self._csrf_token)
