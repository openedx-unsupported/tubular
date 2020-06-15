"""
Sailthru API classes that will call the Sailthru REST API using the Sailthru client.
"""
import os
import logging

import backoff
from sailthru.sailthru_client import SailthruClient
from sailthru.sailthru_error import SailthruClientError

LOG = logging.getLogger(__name__)

SAILTHRU_ERROR_NOT_FOUND = 'User not found with email:'
MAX_ATTEMPTS = int(os.environ.get('RETRY_SAILTHRU_MAX_ATTEMPTS', 5))


class SailthruApi:
    """
    Sailthru API client used to make all Sailthru calls.
    """

    def __init__(self, sailthru_key, sailthru_secret):
        """
        Create a Sailthru client using credentials.
        """
        self._sailthru_client = SailthruClient(sailthru_key, sailthru_secret)

    @backoff.on_exception(
        backoff.expo,
        SailthruClientError,
        max_tries=MAX_ATTEMPTS
    )
    def delete_user(self, learner):
        """
        Delete a user from Sailthru using their email address.
        """
        email = learner.get('original_email', None)
        if not email:
            raise TypeError('Expected an email address for user to delete, but received None.')

        sailthru_response = self._sailthru_client.api_delete("user", {'id': email})

        if not sailthru_response.is_ok():
            error = sailthru_response.get_error()
            if SAILTHRU_ERROR_NOT_FOUND in error.get_message():
                LOG.info("No action taken because no user was found in Sailthru.")
            else:
                error_msg = u"Error attempting to delete user from Sailthru - {}".format(
                    error.get_message()
                ).encode('utf-8')
                LOG.error(error_msg)
                raise Exception(error_msg)

        LOG.info("User successfully deleted from Sailthru.")
