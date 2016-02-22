import datetime
from peewee import *

database_proxy = Proxy()

class User(Model):
    created = DateTimeField(default=datetime.datetime.utcnow)
    following_depth = IntegerField()
    instagram_id = CharField(max_length=20, unique=True)
    is_followed = BooleanField(default=False)
    username = CharField(max_length=30)
    was_followed_at = DateTimeField(null=True)
    were_followers_fetched = BooleanField(default=False)

    class Meta:
        database = database_proxy
        indexes = (
            (('is_followed', 'was_followed_at'), False),
            (('were_followers_fetched', 'following_depth', 'created'), False)
            )

    def get_url(self):
        return 'https://www.instagram.com/{0}/'.format(self.username)
