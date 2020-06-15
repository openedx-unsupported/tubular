"""
Code used to retry calls that fail.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from functools import wraps

MAX_ATTEMPTS = int(os.environ.get('RETRY_MAX_ATTEMPTS', 5))
DELAY_SECONDS = os.environ.get('RETRY_DELAY_SECONDS', 5)
MAX_TIME_SECONDS = os.environ.get('RETRY_MAX_TIME_SECONDS', None)

LOG = logging.getLogger(__name__)


def retry(attempts=MAX_ATTEMPTS, delay_seconds=DELAY_SECONDS, max_time_seconds=MAX_TIME_SECONDS):
    """
    Decorator wraps a function that will attempt to "retry" the function if an exception is raised during execution.
     If no exception is raised, the return value of the wrapped function will be returned to the caller.

    Arguments:
        attempts (int): Number of times to attempt the function
        delay_seconds (int): time in seconds to delay between each attempt
        max_time_seconds (int): Maximum time in seconds to attempt retrying this function

    Returns:
        The return value of the wrapped function

    Raises:
        The final exception raised by the wrapped function
    """

    def retry_decorator(func_to_wrap):
        """
        Implementation of retry decorator.
        """
        if os.environ.get('TUBULAR_RETRY_ENABLED', "true").lower() == "false":
            return func_to_wrap

        @wraps(func_to_wrap)
        def function_wrapper(*args, **kwargs):
            """
            Function to wrap the function which is retried.
            """
            return LifecycleManager(attempts, delay_seconds, max_time_seconds).execute(func_to_wrap, *args, **kwargs)

        return function_wrapper

    return retry_decorator


class LifecycleManager:
    """
    Manages the lifecycle of a function to be retried using the retry wrapper: tubular.utils.retry.retry
    """

    def __init__(self, max_attempts, delay_seconds, max_time_seconds):
        """
        Create a lifecycle manager. Validates arguments.

        TODO: Allow caller to specify a list of exceptions that can be checked for and return if any of those are raised
        TODO: Allow caller to pass in a validation function that can be used to evaluate the return value of the wrapped
              function
        TODO: Exponential back off with a ceiling might be another nice feature.

        Arguments:
            max_attempts (int): number of times to attempt the wrapped function. Must be >= 1
            delay_seconds (int): How long to delay between calls to the wrapped function. Must be >= 0
            max_time_seconds (int): maximum number of seconds to keep attempting to call this function. Default: None
                                     When None the method will continue to be called until max_attempts is reached.
        """
        if max_attempts < 1:
            raise RetryException(
                "Must specify a max_attempts number greater than or equal to 1. Value: {0}".format(max_attempts))

        if delay_seconds < 0:
            raise RetryException(
                "Must specify a delay_seconds number greater than or equal to 0. Value: {0}".format(delay_seconds))

        if max_time_seconds is not None and max_time_seconds > delay_seconds:
            LOG.warning(
                "max_time_seconds {0} is greater than delay_seconds {1}. "
                "This will cause this method to only be attempted once".format(
                    max_time_seconds, delay_seconds
                )
            )

        self._current_attempt_number = 0
        self._max_datetime = datetime.utcnow() + timedelta(0, max_time_seconds) if max_time_seconds else None
        # pylint: disable=round-builtin
        self.max_attempts = round(max_attempts)
        self.delay_seconds = round(delay_seconds)

    def max_attempts_reached(self):
        """
        Returns:
            bool: True if the retry has reached its maximum number of attempts
                  False if the current attempt is less than the number of attempts
        """
        return self._current_attempt_number > self.max_attempts

    def max_time_reached(self):
        """
        Returns:
            bool: True if the maximum runtime of the retry has been met or exceeded
                  False if the max_time was not set or if the max time has not yet been reached
        """
        return self._max_datetime and self._max_datetime - datetime.utcnow() < timedelta(0, 0, 0)

    def get_delay_time(self):
        """
        Returns:
            int: seconds to delay
        """
        return self.delay_seconds

    def sleep(self):
        """
        Sleep this lifecycle manager
        """
        time.sleep(self.get_delay_time())

    def done(self):
        """
        Returns:
            True if the max_attempts have been reached or the max_time has been reached
            False otherwise
        """
        return self.max_attempts_reached() or self.max_time_reached()

    def execute(self, func_to_retry, *args, **kwargs):
        """
        Execute the wrapped function retrying the specified number of attempts.

        If successful the result of the function will be returned.
        If the call ultimately fails with an Exception that exception will be raised

        Arguments:
            func_to_retry (function): the function to execute
            args(list<any>): Arguments to the wrapped function
            kwargs(dict<str:any>): Keyword arguments to the wrapped function

        """
        while not self.done():
            try:
                self._current_attempt_number += 1
                LOG.debug("Attempting function: {0} try number: {1}".format(
                    func_to_retry.__name__,
                    self._current_attempt_number
                ))
                result = func_to_retry(*args, **kwargs)
                break
            except Exception as err:  # pylint: disable=broad-except
                LOG.warning(
                    "Error executing function {0}, Exception type: {1} Message: {2}".format(
                        func_to_retry.__name__, err.__class__, err
                    ))
                result = err

            if not self.max_attempts_reached() and not self.max_time_reached():
                self.sleep()

        if isinstance(result, Exception):
            raise result

        return result


class RetryException(Exception):
    """
    Exception to use in retry tests.
    """
