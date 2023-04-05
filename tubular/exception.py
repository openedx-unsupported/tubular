"""
Exceptions used by various utilities.
"""


class TimeoutException(Exception):
    pass


class ImageNotFoundException(Exception):
    pass

class InvalidAMIID(Exception):
    pass


class MultipleImagesFoundException(Exception):
    pass


class MissingTagException(Exception):
    pass


class BackendError(Exception):
    pass


class BackendDataError(BackendError):
    pass


class JavaSocketException(BackendError):
    pass


class ResourceDoesNotExistException(Exception):
    pass


class ASGDoesNotExistException(ResourceDoesNotExistException):
    pass


class ClusterDoesNotExistException(ResourceDoesNotExistException):
    pass


class CannotDeleteActiveASG(Exception):
    pass


class CannotDisableActiveASG(Exception):
    pass


class CannotDeleteLastASG(Exception):
    pass


class ASGCountZeroException(Exception):
    pass


class InvalidUrlException(Exception):
    pass


class RateLimitedException(Exception):
    pass


class HttpDoesNotExistException(Exception):
    """
    Called when the server sends a 404 error.
    """
    pass


class HTTPClientError(Exception):
    """
    Called when the server sends a 404 error.
    """
    pass