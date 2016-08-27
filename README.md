# InstaBot

Instagram bot written in Python 3.5 that cycles through specified hashtags and automatically likes pictures with those hashtags to get more followers. The bot also follows people and unfollows them after specified period of time. Unfollowed people are saved in DB to prevent following them again. To find new people to follow it uses list of followers of people you have followed.

During installation process it saves people followed by you as "followed long time ago" and unfollows them at the first start.

## Deployment

    $ virtualenv --python=/usr/bin/python3 instabotenv
    $ cd instabotenv
    $ source bin/activate
    (instabotenv) $ git clone https://github.com/quasiyoke/InstaBot.git
    (instabotenv) $ cd InstaBot
    (instabotenv) $ pip install -r requirements.txt

Create MySQL DB:

```sql
CREATE DATABASE IF NOT EXISTS instagram CHARACTER SET utf8 COLLATE utf8_general_ci;
CREATE USER instabot@localhost IDENTIFIED BY 'GT8H!b]5,9}A7';
GRANT ALL ON instagram.* TO instabot@localhost;
```

Create `configuration.yml` file containing your credentials, e.g.:

```yaml
credentials:
  client_id: "1eac8774163c2fc938db3a0ee82a6873"
  username: "your_username"
  password: "eKeFB2;AW6fS}z"
db:
  host: "localhost"
  name: "instagram"
  user: "instabot"
  password: "GT8H!b]5,9}A7"
following_hours: 120
hashtags:
  - I
  - люблю
  - Python
instagram:
  limit_sleep_time_coefficient: 1.3
  limit_sleep_time_min: 30
  success_sleep_time_coefficient: 0.5
  success_sleep_time_max: 6
  success_sleep_time_min: 4
logging:
  version: 1
  formatters:
    simple:
      class: logging.Formatter
      format: "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
  handlers:
    console:
      class: logging.StreamHandler
      level: DEBUG
      formatter: simple
    file:
      class: logging.handlers.RotatingFileHandler
      level: DEBUG
      formatter: simple
      filename: log.log
      maxBytes: 10485760
      backupCount: 10
      encoding: utf-8
  loggers:
    instabot:
      level: DEBUG
  root:
    level: DEBUG
    handlers:
      - console
users_to_follow_cache_size: 300
```

Where:

* `following_hours` — how long users will stay followed.
* `hashtags` — list of hashtags to get photos to like. Optional. By default bot won't like anything.
* `logging` — logging setup as described in [this howto](https://docs.python.org/3/howto/logging.html).
* `users_to_follow_cache_size` — how much users should be fetched for following. The cache is being filled in once a minute. Optional. By default bot won't follow anybody.

Create necessary DB tables:

    (instabotenv) $ ./instabot_runner.py install configuration.yml

Run:

    (instabotenv) $ ./instabot_runner.py configuration.yml
