import asyncio

class Counter:
    def __init__(self):
        self._counter = {}

    def clear(self):
        self._counter.clear()

    def increment(self, key):
        value = self._counter.get(key, 0)
        self._counter[key] = value + 1

    def report(self, prefix):
        LOGGER.info('%s %s', prefix, str(self._counter))

class StatsService:
    def __init__(self):
        self._hourly_counter = Counter()
        self._daily_counter = Counter()
        type(self)._instance = self

    @classmethod
    def get_instance(cls):
        return cls._instance

    @asyncio.coroutine
    def run(self):
        hour = 0
        while True:
            asyncio.sleep(60 * 60)
            hour += 1
            if hour % 24 == 0:
                self._daily_counter.report('Daily stats #{0}'.format(hour / 24))
                self._daily_counter.clear()
            else:
                self._hourly_counter.report('Hourly stats #{0}'.format(hour))
            self._hourly_counter.clear()

    def increment(self, key):
        self._hourly_counter.increment(key)
        self._daily_counter.increment(key)
