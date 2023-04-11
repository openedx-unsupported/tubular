"""
Exceptions used by various utilities.
"""


class TimeoutException(Exception):
    pass


class ImageNotFoundException(Exception):
    pass


class InvalidAMIID(Exception):
    def __init__(self, ami_id):
        self.ami_id = ami_id
        self.message = f"AMI ID '{ami_id}' not found in the current region."
        super().__init__(self.message)

    def __str__(self):
        return self.message


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
