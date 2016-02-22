import logging
import sys
import yaml

LOGGER = logging.getLogger('instabot')

class Configuration:
    def __init__(self, filename):
        try:
            with open(filename, 'r') as f:
                configuration = yaml.safe_load(f)
        except (IOError, OSError, ValueError) as e:
            sys.exit('Can\'t obtain configuration: %s' % e)
        try:
            self.db_host = configuration['db']['host']
            self.db_name = configuration['db']['name']
            self.db_user = configuration['db']['user']
            self.db_password = configuration['db']['password']
            self.following_hours = configuration['following_hours']
            self.instagram_client_id = configuration['credentials']['client_id']
            self.instagram_limit_sleep_time_coefficient = \
                configuration['instagram']['limit_sleep_time_coefficient']
            self.instagram_limit_sleep_time_min = \
                configuration['instagram']['limit_sleep_time_min']
            self.instagram_success_sleep_time_coefficient = \
                configuration['instagram']['success_sleep_time_coefficient']
            self.instagram_success_sleep_time_max = \
                configuration['instagram']['success_sleep_time_max']
            self.instagram_success_sleep_time_min = \
                configuration['instagram']['success_sleep_time_min']
            self.instagram_username = configuration['credentials']['username']
            self.instagram_password = configuration['credentials']['password']
            self.logging = configuration['logging']
        except (KeyError, TypeError) as e:
            sys.exit('Configuration is not fully specified. {} is missed.'.format(e))
        self.hashtags = configuration.get('hashtags', [])
        self.users_to_follow_cache_size = configuration.get('users_to_follow_cache_size', 0)
        try:
            self.following_hours = int(self.following_hours)
            self.users_to_follow_cache_size = int(self.users_to_follow_cache_size)
        except ValueError as e:
            sys.exit('Some integer value is specified wrong: {}'.format(e))
