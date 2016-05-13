"""
Exceptions used by various utilities.
"""

class TimeoutException(Exception):
    pass


class ImageNotFoundException(Exception):
    pass


class MissingTagException(Exception):
    pass


class BackendError(Exception):
    pass


class BackendDataError(BackendError):
    pass
