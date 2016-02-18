# Instagram Bot

A simple Instagram bot that cycles through hashtags listed at a file and automatically likes pictures with those hashtags to get more followers.

## Setup

At first, get the source. Clone this repository:

    $ git clone https://github.com/quasiyoke/InstaBot.git

### Requirements

You can install all needed requirements with single command:

    $ pip install -r requirements.txt

### Configuration

Create `configuration.yml` file containing your information, e.g.:

```yaml
credentials:
  client_id: "1eac8774163c2fc938db3a0ee82a6873"
  login: "your_login"
  password: "eKeFB2;AW6fS}z"
db:
  host: "localhost"
  name: "instagram"
  user: "instabot"
  password: "GT8H!b]5,9}A7"
following_hours: 120
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
  root:
    level: DEBUG
    handlers:
      - console
hashtags:
  - I
  - love
  - Python
```

Execute this at MySQL console:

    CREATE DATABASE IF NOT EXISTS instagram CHARACTER SET utf8 COLLATE utf8_general_ci;
    CREATE USER instabot@localhost IDENTIFIED BY 'GT8H!b]5,9}A7';
    GRANT ALL ON instagram.* TO instabot@localhost;

## Launching

Run:

    $ ./instabot_runner.py
