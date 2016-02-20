class APIError(Exception):
    def __init__(self, code):
        super(APIError, self).__init__(str(code))

class APIJSONError(Exception):
    pass

class APILimitError(APIJSONError):
    pass

class APINotAllowedError(APIJSONError):
    pass

class DBError(Exception):
    pass
