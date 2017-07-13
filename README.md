# InstaBot

Instagram bot written in Python 3 that cycles through specified hashtags and automatically likes pictures with those hashtags to get more followers. The bot also follows people and unfollows them after specified period of time. Unfollowed people are saved in DB to prevent following them again. To find new people to follow it uses list of followers of people you have followed.

During installation process it saves people followed by you as "followed long time ago" and unfollows them at the first start.

The bot doesn't use Instagram API so all credentials you need are your login and password.

## Deployment

```sh
docker network create \
    --subnet=172.21.0.0/24 \
    instabot
docker run \
    --name=instabot-mysql \
    --net=instabot \
    --ip=172.21.0.2 \
    --env="MYSQL_ROOT_PASSWORD=ZEbMKcFQppk8m8PR3b" \
    --env="MYSQL_DATABASE=instabot" \
    --env="MYSQL_USER=instabot" \
    --env="MYSQL_PASSWORD=KbWj0Eua78YGLNLf3K" \
    --volume=`pwd`/lib:/var/lib/mysql \
    --detach \
    mysql:5.7
docker build --tag=instabot .
```

Create MySQL DB:

```sql
CREATE DATABASE IF NOT EXISTS instagram CHARACTER SET utf8 COLLATE utf8_general_ci;
CREATE USER instabot@localhost IDENTIFIED BY 'GT8H!b]5,9}A7';
GRANT ALL ON instagram.* TO instabot@localhost;
```

Create `configuration.yml` file containing your credentials, e.g.:

```yaml
credentials:
  username: "your_username"
  password: "eKeFB2;AW6fS}z"
db:
  host: "172.21.0.2"
  name: "instabot"
  user: "instabot"
  password: "KbWj0Eua78YGLNLf3K"
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

Now you may run the bot:

```sh
docker run \
    --name=instabot \
    --net=instabot \
    --ip=172.21.0.10 \
    --volume=`pwd`/configuration:/configuration \
    --detach \
    instabot
```
