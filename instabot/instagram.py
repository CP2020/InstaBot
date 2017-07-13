import asyncio
import logging
import json
import re
import urllib.parse

from .errors import APIError, APILimitError, \
    APINotAllowedError, APINotFoundError, APIFailError
from aiohttp import ClientSession
from http import HTTPStatus

BASE_URL = 'https://www.instagram.com/'
LOGGER = logging.getLogger('instabot.instagram')
USER_AGENT = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:54.0) Gecko/20100101 Firefox/54.0'


class Client:
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
                'ig_vw': '1920',
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
            APIFailError
            APIJSONError
            APILimitError
            APINotAllowedError
            APINotFoundError

        """
        if referer is not None:
            self._referer = referer
        url = f'{BASE_URL}{url}'
        headers = {
            'Referer': self._referer,
            'X-CSRFToken': self._csrf_token,
            }
        async with self._session.post(
            url,
            data=data,
            headers=headers,
            ) as response:
            if response.status == HTTPStatus.NOT_FOUND:
                response.close()
                await self._sleep_success()
                raise APINotFoundError(f'AJAX response status code is 404 for {url}')
            elif HTTPStatus.INTERNAL_SERVER_ERROR <= response.status:
                response.close()
                await self._sleep_success()
                raise APIError(response.status)
            text = await response.text()
            try:
                response_dict = json.loads(text)
            except ValueError as err:
                reason = f'AJAX request to {url} is not JSON: {err} Response ({response.status}): \"{text}\"'
                if response.status == HTTPStatus.OK:
                    await self._sleep_success()
                    raise APIError(reason)
                elif response.status == HTTPStatus.BAD_REQUEST:
                    await self._sleep_success()
                    raise APINotAllowedError(reason)
                else:
                    await self._sleep_success()
                    raise APIError(reason)
        status = response_dict.get('status')
        if status == 'fail':
            message = response_dict.get('message')
            if isinstance(message, str) and 'temporarily blocked' in message:
                await self._sleep_limit()
                raise APILimitError(f'AJAX request to {url} was blocked: {response_dict}')
            raise APIFailError(f'AJAX request to {url} was failed: {response_dict}')
        elif status != 'ok':
            raise APIError(f'AJAX request to {url} is not OK: {response_dict}')
        LOGGER.debug(f'Request: {url} Response: {response_dict}')
        await self._sleep_success()
        return response_dict

    async def _do_login(self):
        """Logins client session.

        Raises:
            APIJSONError
            APILimitError
            APINotAllowedError
            APIError

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
        try:
            self.id = self._session.cookies['ds_user_id'].value
        except KeyError as err:
            reason = 'Can\'t obtain user ID from cookies.'
            LOGGER.exception(reason)
            raise APIError(reason) from err

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

    async def _get_followers_page(self, user, cursor=None):
        """
        Args:
            user (User): User whose followers should be fetched
            cursor: The next page to retrieve, if possible.
        :param user:
        :param cursor:
        :return:
        """
        cursor = 'first(20)' if cursor is None else \
            'after({}, 20)'.format(cursor)
        query = '''ig_user({user_instagram_id}) {{
            followed_by.{cursor} {{
                count,
                page_info {{
                    end_cursor,
                    has_next_page
                }},
                nodes {{
                    id,
                    is_verified,
                    followed_by {{count}},
                    follows {{count}},
                    followed_by_viewer,
                    follows_viewer,
                    requested_by_viewer,
                    full_name,
                    profile_pic_url,
                    username
                }}
            }}
        }}''' \
            .format(user_instagram_id=user.instagram_id, cursor=cursor)
        data = {'q': query, 'ref': 'relationships::follow_list'}
        response = await self._ajax('query/', data, referer=user.get_url())
        try:
            followers = response['followed_by']['nodes']
            page_info = response['followed_by']['page_info']
            end_cursor = page_info['end_cursor']
            has_next_page = page_info['has_next_page']
        except (KeyError, TypeError) as e:
            raise APINotAllowedError(
                'Instagram have given unexpected data in '
                '`_get_followers_page`. Response JSON: {response} '
                'Error: {error}'.format(
                    response=response,
                    error=e,
                )
            )
        return followers, end_cursor, has_next_page

    async def get_media_by_hashtag(self, hashtag):
        """Fetches some media about specified hashtag.

        Returns:
            List of media IDs (strings)

        Args:
            hashtag (str): Hashtag to fetch

        Raises:
            APIError
            IOError
            OSError
            ClientResponseError

        """
        url = '{}explore/tags/{}/'.format(
            BASE_URL,
            urllib.parse.quote(hashtag.encode('utf-8')),
            )
        response = await self._session.get(url)
        response = await response.read()
        response = response.decode('utf-8', errors='ignore')
        match = re.search(
            r'<script type="text/javascript">[\w\.]+\s*=\s*([^<]+);'
            '</script>',
            response,
            )
        if match is None:
            raise APIError('Can\'t find JSON in the response: {}', response)
        try:
            response = json.loads(match.group(1))
        except ValueError as e:
            raise APIError('Can\'t parse response JSON: {}'.format(e))
        try:
            media = response['entry_data']['TagPage'][0]['tag']
            media = media['media']['nodes']
            media = [media_item['id'] for media_item in media]
        except (KeyError, TypeError) as e:
            raise APIError(
                'Can\'t obtain media from response JSON: {}'.format(e),
                )
        LOGGER.debug(
            '{} media about \"{}\" were fetched'.format(len(media), hashtag),
            )
        return media

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
        pages_to_fetch = 3
        followers = []
        get_next = True
        cursor = None  # Eventually we will check if we have a
        # cached page and use that.
        LOGGER.debug('Fetching followers of {}'.format(user.username))
        while get_next and pages_to_fetch > 0:
            next_followers, cursor, get_next = await self._get_followers_page(
                user=user,
                cursor=cursor,
                )
            followers.extend(next_followers)
            pages_to_fetch -= 1
            await asyncio.sleep(5)
        # TODO: Cache cursor for continuation of this, if needed.
        LOGGER.debug('Fetched {} followers of {}'
                     .format(len(followers), user.username))
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
        """Opens given URL (HTTP GET).

        Args:
            url (str)

        Returns:
            str: Response.

        """
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
        """Unfollows certain user.

        Raises:
            APIError
            APIFailError
            APIJSONError
            APILimitError
            APINotAllowedError
            APINotFoundError

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
        except APIFailError as e:
            raise APIFailError(
                'API troubles during unfollowing {}. {}'
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
