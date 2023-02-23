"""
Amplitude API class that is used to delete user from Amplitude.
"""
import logging
import requests
import json
import backoff
import os

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = int(os.environ.get("RETRY_MAX_ATTEMPTS", 5))


class AmplitudeException(Exception):
    """
    AmplitudeException will be raised there is fatal error and is not recoverable.
    """
    pass


class AmplitudeRecoverableException(AmplitudeException):
    """
    AmplitudeRecoverableException will be raised when request can be retryable.
    """
    pass


class AmplitudeApi:
    """
    Amplitude API is used to handle communication with Amplitude Api's.
    """

    def __init__(self, amplitude_api_key, amplitude_secret_key):
        self.amplitude_api_key = amplitude_api_key
        self.amplitude_secret_key = amplitude_secret_key
        self.base_url = "https://amplitude.com/"
        self.delete_user_path = "api/2/deletions/users"

    def auth_headers(self):
        """
        Returns authorization headers suitable for passing to the requests library.

        Returns:
            Dict: Returns authorization headers dictionary.
        """
        return {
            "Authorization": "Basic {api_key}:{secret_key}".format(api_key=self.amplitude_api_key, secret_key=self.amplitude_secret_key),
            "Content-Type": "application/json"
        }


    @backoff.on_exception(
        backoff.expo,
        AmplitudeRecoverableException,
        max_tries = MAX_ATTEMPTS,
    )
    def delete_user(self, user):
        """
        This function send an API request to delete user from Amplitude. It then parse the response and
        try again if it is recoverable.

        Returns:
            None

        Args:
            user (dict): raw data of user to delete.

        Raises:
          AmplitudeException: if the error from amplitude is unrecoverable/unretryable.
          AmplitudeRecoverableException: if the error from amplitude is recoverable/retryable.
        """
        response = requests.post(
            self.base_url + self.delete_user_path,
            headers = self.auth_headers(),
            data = json.dumps({
                "user_ids": [user["user"]["id"]],
                "requester": "user-retirement-pipeline"
            })
        )

        if response.status_code == 200:
            logger.info("Amplitude user deletion succeeded")
            return

        # We have some sort of error. Parse it, log it, and retry as needed.
        error_msg = "Amplitude user deletion failed due to {reason}".format(reason=response.reason)
        logger.error(error_msg)
        # Status 429 is returned when there are too many requests and can be resolved in retrying sending
        # request.
        if response.status_code == 429 or 500 <= response.status_code < 600:
            raise AmplitudeRecoverableException(error_msg)
        else:
            raise AmplitudeException(error_msg)
