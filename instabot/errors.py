class APIError(Exception):
    def __init__(self, response):
        super(APIError, self).__init__(
            '{0} ({1}): {2}'.format(
                response['meta']['code'],
                response['meta']['error_type'],
                response['meta']['error_message'],
                )
            )

class APILimitError(APIError):
    pass

class APINotAllowedError(APIError):
    pass

class DBError(Exception):
    pass
