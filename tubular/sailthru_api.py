"""
Sailthru API classes that will call the Sailthru REST API using the Sailthru client.
"""
import logging
from six import text_type

from sailthru.sailthru_client import SailthruClient
from sailthru.sailthru_error import SailthruClientError

log = logging.getLogger(__name__)

SAILTHRU_ERROR_NOT_FOUND = 'User not found with email:'


class SailthruApi(object):
    """
    Sailthru API client used to make all Sailthru calls.
    """
    def __init__(self, sailthru_key, sailthru_secret):
        """
        Create a Sailthru client using credentials.
        """
        self._sailthru_client = SailthruClient(sailthru_key, sailthru_secret)

    def delete_user(self, learner):
        """
        Delete a user from Sailthru using their email address.
        """
        email = learner.get('original_email', None)
        if not email:
            raise TypeError('Expected an email address for user to delete, but received None.')

        try:
            sailthru_response = self._sailthru_client.api_delete("user", {'id': email})
        except SailthruClientError as exc:
            error_msg = u"Exception attempting to delete user {} from Sailthru - {}".format(
                email, text_type(exc)
            ).encode('utf-8')
            log.error(error_msg)
            raise Exception(error_msg)

        if not sailthru_response.is_ok():
            error = sailthru_response.get_error()
            if SAILTHRU_ERROR_NOT_FOUND in error.get_message():
                skip_msg = u"No action taken because no profile was found - {}".format(
                    error.get_message()
                ).encode('utf-8')
                log.info(skip_msg)
            else:
                error_msg = u"Error attempting to delete user {} from Sailthru - {}".format(
                    email, error.get_message()
                ).encode('utf-8')
                log.error(error_msg)
                raise Exception(error_msg)

        log.info("Email address %s successfully deleted from Sailthru.", email)
