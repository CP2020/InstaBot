import logging
import sys
from .errors import DBError
from instabot import user
from peewee import *
from playhouse.shortcuts import RetryOperationalError

LOGGER = logging.getLogger('instabot')


class RetryingMySQLDatabase(RetryOperationalError, MySQLDatabase):
    '''
    Automatically reconnecting database class.
    @see {@link
    http://docs.peewee-orm.com/en/latest/peewee/database.html#automatic-reconnect}
    '''
    pass


def get_db(configuration):
    '''
    @raise DBError
    '''
    db = RetryingMySQLDatabase(
        configuration.db_name,
        host=configuration.db_host,
        user=configuration.db_user,
        password=configuration.db_password,
        )
    # Connect to database just to check if configuration has errors.
    try:
        db.connect()
    except DatabaseError as e:
        sys.exit('DatabaseError during connecting to database: {0}'.format(e))
    db.close()
    user.database_proxy.initialize(db)
    return db
