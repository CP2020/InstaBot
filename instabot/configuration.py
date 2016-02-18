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
            self.instagram_login = configuration['credentials']['login']
            self.instagram_password = configuration['credentials']['password']
            self.logging = configuration['logging']
            self.hashtags = configuration['hashtags']
        except KeyError as e:
            sys.exit('Configuration is not fully specified: %s' % e)
        try:
            self.following_hours = int(self.following_hours)
        except ValueError as e:
            sys.exit('following_hours are specified wrong: %s' % e)
        if len(self.hashtags) == 0:
            sys.exit('Specify at least one hashtag, please')
