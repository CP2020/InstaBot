import asyncio
import logging
import json
from .errors import APIError, APILimitError, \
    APINotAllowedError, APINotFoundError
from aiohttp import ClientSession

BASE_URL = 'https://www.instagram.com/'
LOGGER = logging.getLogger('instabot.instagram')
USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:48.0) ' \
    'Gecko/20100101 Firefox/48.0'


class Client(object):
    def __init__(self, configuration):
        self._limit_sleep_time_coefficient = configuration \
            .instagram_limit_sleep_time_coefficient
        self._limit_sleep_time_min = configuration \
            .instagram_limit_sleep_time_min
        self._success_sleep_time_coefficient = configuration \
            .instagram_success_sleep_time_coefficient
        self._success_sleep_time_max = configuration \
            .instagram_success_sleep_time_max
        self._success_sleep_time_min = configuration \
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
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._do_login())

    async def _ajax(self, url, data=None, referer=None):
        """Simulates AJAX request.

        Args:
            url (str): URL path. e.g.: 'query/'
            data (dict, optional)
            referer (str, optional): Last visited URL.

        Raises:
            APIError
            APIJSONError
            APILimitError
            APINotAllowedError
            APINotFoundError

        """
        if referer is not None:
            self._referer = referer
        url = BASE_URL + url
        headers = {
            'Referer': self._referer,
            'X-CSRFToken': self._csrf_token,
            }
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

    async def _do_login(self):
        """
        @raise APIJSONError
        @raise APILimitError
        @raise APINotAllowedError
        @raise APIError
        """
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
        """
        @raise APIJSONError
        @raise APILimitError
        @raise APINotAllowedError
        @raise APINotFoundError
        @raise APIError
        """
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
        """Fetches information about people followed by given user.

        Args:
            user (User): Whose subscriptions should be fetched.

        Returns:
            List of dicts containing following fields:
            {
                'id': '123',
                'username': 'foobar',
            }

        Raises:
            APIJSONError
            APILimitError
            APINotAllowedError
            APIError

        """
        single_response_size = 50

        response = await self._ajax(
            'query/',
            {
                'q': 'ig_user({id}) {{  follows.first({count}) {{    count,'
                '    page_info {{      end_cursor,      has_next_page    }},'
                '    nodes {{      id,      is_verified,'
                '      followed_by_viewer,      requested_by_viewer,'
                '      full_name,      profile_pic_url,'
                '      username    }}  }}}}'
                .format(
                    id=user.instagram_id,
                    count=single_response_size,
                    ),
                'ref': 'relationships::follow_list',
                },
            referer=user.get_url(),
            )
        followed = response['follows']['nodes']
        while response['follows']['page_info']['has_next_page']:
            end_cursor = response['follows']['page_info']['end_cursor']
            response = await self._ajax(
                'query/',
                {
                    'q': 'ig_user({id}) {{  follows.after({end_cursor},'
                    ' {count}) {{    count,    page_info {{      end_cursor,'
                    '      has_next_page    }},    nodes {{      id,'
                    '      is_verified,      followed_by_viewer,'
                    '      requested_by_viewer,      full_name,'
                    '      profile_pic_url,      username    }}  }}}}'
                    .format(
                        id=user.instagram_id,
                        end_cursor=end_cursor,
                        count=single_response_size,
                        ),
                    'ref': 'relationships::follow_list',
                    },
                referer=user.get_url(),
                )
            followed.extend(response['follows']['nodes'])
        LOGGER.debug('{} followed users were fetched'.format(len(followed)))
        return followed

    async def get_some_followers(self, user):
        """Fetches some amount of followers of given user.

        Args:
            user (User): Whose followers should be fetched.

        Returns:
            List of dicts containing following fields:
            {
                'id': '123',
                'username': 'foobar',
            }

        Raises:
            APIJSONError
            APILimitError
            APINotAllowedError
            APIError

        """
        single_response_size = 50

        response = await self._ajax(
            'query/',
            {
                'q': 'ig_user({id}) {{  followed_by.first({count}) {{'
                '    count,    page_info {{      end_cursor,'
                '      has_next_page    }},    nodes {{      id,'
                '      is_verified,      followed_by_viewer,'
                '      requested_by_viewer,      full_name,'
                '      profile_pic_url,      username    }}  }}}}'
                .format(
                    id=user.instagram_id,
                    count=single_response_size,
                    ),
                'ref': 'relationships::follow_list',
                },
            referer=user.get_url(),
            )
        try:
            followers = response['followed_by']['nodes']
        except (KeyError, TypeError) as e:
            raise APINotAllowedError(
                'Instagram have given unexpected data in '
                '`get_some_followers`. Response JSON: {response} '
                'Error: {error}'
                .format(
                    response=response,
                    error=e,
                    )
                )
        return followers

    async def like(self, media):
        """
        @raise APIError
        @raise APIJSONError
        @raise APILimitError
        @raise APINotAllowedError
        @raise APINotFoundError
        """
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
        """
        @raise APIError
        @raise APIJSONError
        @raise APILimitError
        @raise APINotAllowedError
        @raise APINotFoundError
        """
        try:
            await self._ajax(
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
