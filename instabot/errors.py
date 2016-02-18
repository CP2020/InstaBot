class APIError(Exception):
    def __init__(self, message, error):
        self.message = message + ' ' + str(error)
        self.status_code = error.getcode()

class APILimitError(Exception):
    pass

class DBError(Exception):
    pass
