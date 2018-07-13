"""
edX API classes which call edX service REST API endpoints using the edx-rest-api-client module.
"""
import logging
from contextlib import contextmanager

import backoff
from six import text_type
from slumber.exceptions import HttpClientError, HttpServerError, HttpNotFoundError

from edx_rest_api_client.client import EdxRestApiClient


LOG = logging.getLogger(__name__)

OAUTH_ACCESS_TOKEN_URL = "/oauth2/access_token"


class EdxGatewayTimeoutError(Exception):
    """
    Exception used to indicate a 504 server error was returned.
    Differentiates from other 5xx errors.
    """
    pass


class BaseApiClient(object):
    """
    API client base class used to submit API requests to a particular web service.
    """
    append_slash = True
    _client = None

    def __init__(self, lms_base_url, api_base_url, client_id, client_secret):
        """
        Retrieves OAuth access token from the LMS and creates REST API client instance.
        """
        self.api_base_url = api_base_url
        access_token, __ = self.get_access_token(lms_base_url, client_id, client_secret)
        self.create_client(access_token)

    def create_client(self, access_token):
        """
        Creates and stores the EdxRestApiClient that we use to actually make requests.
        """
        self._client = EdxRestApiClient(
            self.api_base_url,
            jwt=access_token,
            append_slash=self.append_slash
        )

    @staticmethod
    def get_access_token(oauth_base_url, client_id, client_secret):
        """
        Returns an access token and expiration date from the OAuth provider.

        Returns:
            (str, datetime)
        """
        try:
            return EdxRestApiClient.get_oauth_access_token(
                oauth_base_url + OAUTH_ACCESS_TOKEN_URL, client_id, client_secret, token_type='jwt'
            )
        except HttpClientError as err:
            LOG.error("API Error: {}".format(err.content))
            raise


def _backoff_handler(details):
    """
    Simple logging handler for when timeout backoff occurs.
    """
    LOG.info('Trying again in {wait:0.1f} seconds after {tries} tries calling {target}'.format(**details))


def _wait_one_minute():
    """
    Backoff generator that waits for 60 seconds.
    """
    return backoff.constant(interval=60)


def _exception_not_internal_svr_error(exc):
    """
    Giveup method that gives up backoff upon any non-5xx and 504 server errors.
    """
    return not (500 <= exc.response.status_code < 600 and exc.response.status_code != 504)


def _retry_lms_api():
    """
    Decorator which enables retries with sane backoff defaults for LMS APIs.
    """
    def inner(func):  # pylint: disable=missing-docstring
        func_with_backoff = backoff.on_exception(
            backoff.expo,
            HttpServerError,
            max_time=600,  # 10 minutes
            giveup=_exception_not_internal_svr_error,
            # Wrap the actual _backoff_handler so that we can patch the real one in unit tests.  Otherwise, the func
            # will get decorated on import, embedding this handler as a python object reference, precluding our ability
            # to patch it in tests.
            on_backoff=lambda details: _backoff_handler(details)  # pylint: disable=unnecessary-lambda
        )
        func_with_timeout_backoff = backoff.on_exception(
            _wait_one_minute,
            EdxGatewayTimeoutError,
            max_tries=2,
            # Wrap the actual _backoff_handler so that we can patch the real one in unit tests.  Otherwise, the func
            # will get decorated on import, embedding this handler as a python object reference, precluding our ability
            # to patch it in tests.
            on_backoff=lambda details: _backoff_handler(details)  # pylint: disable=unnecessary-lambda
        )
        return func_with_backoff(func_with_timeout_backoff(func))
    return inner


@contextmanager
def correct_exception():
    """
    Context manager that differentiates 504 gateway timeouts from other 5xx server errors.
    Re-raises any unhandled exceptions.
    """
    try:
        yield
    except HttpServerError as err:
        if err.response.status_code == 504:  # pylint: disable=no-member
            # Differentiate gateway errors so different backoff can be used.
            raise EdxGatewayTimeoutError(text_type(err))
        else:
            raise err
    except HttpClientError as err:
        try:
            LOG.error("API Error: {}".format(err.content))
        except AttributeError:
            LOG.error("API Error: {}".format(text_type(err)))
        raise err


class LmsApi(BaseApiClient):
    """
    LMS API client with convenience methods for making API calls.
    """
    @_retry_lms_api()
    def learners_to_retire(self, states_to_request, cool_off_days=7):
        """
        Retrieves a list of learners awaiting retirement actions.
        """
        params = {
            'cool_off_days': cool_off_days,
            'states': states_to_request
        }
        with correct_exception():
            return self._client.api.user.v1.accounts.retirement_queue.get(**params)

    @_retry_lms_api()
    def get_learner_retirement_state(self, username):
        """
        Retrieves the given learner's retirement state.
        """
        with correct_exception():
            return self._client.api.user.v1.accounts(username).retirement_status.get()

    @_retry_lms_api()
    def update_learner_retirement_state(self, username, new_state_name, message):
        """
        Updates the given learner's retirement state to the retirement state name new_string
        with the additional string information in message (for logging purposes).
        """
        params = {
            'data': {
                'username': username,
                'new_state': new_state_name,
                'response': message
            },
        }
        with correct_exception():
            return self._client.api.user.v1.accounts.update_retirement_status.patch(**params)

    @_retry_lms_api()
    def retirement_deactivate_logout(self, learner):
        """
        Performs the user deactivation and forced logout step of learner retirement
        """
        params = {'data': {'username': learner['original_username']}}
        with correct_exception():
            return self._client.api.user.v1.accounts.deactivate_logout.post(**params)

    @_retry_lms_api()
    def retirement_retire_forum(self, learner):
        """
        Performs the forum retirement step of learner retirement
        """
        # api/discussion/
        params = {'data': {'username': learner['original_username']}}
        try:
            with correct_exception():
                return self._client.api.discussion.v1.accounts.retire_forum.post(**params)
        except HttpNotFoundError:
            return True

    @_retry_lms_api()
    def retirement_retire_mailings(self, learner):
        """
        Performs the email list retirement step of learner retirement
        """
        params = {'data': {'username': learner['original_username']}}
        with correct_exception():
            return self._client.api.user.v1.accounts.retire_mailings.post(**params)

    @_retry_lms_api()
    def retirement_unenroll(self, learner):
        """
        Unenrolls the user from all courses
        """
        params = {'data': {'username': learner['original_username']}}
        with correct_exception():
            return self._client.api.enrollment.v1.unenroll.post(**params)

    # This endpoint additionaly returns 500 when the EdxNotes backend service is unavailable.
    @_retry_lms_api()
    def retirement_retire_notes(self, learner):
        """
        Deletes all the user's notes (aka. annotations)
        """
        params = {'data': {'username': learner['original_username']}}
        with correct_exception():
            return self._client.api.edxnotes.v1.retire_user.post(**params)

    @_retry_lms_api()
    def retirement_lms_retire_misc(self, learner):
        """
        Deletes, blanks, or one-way hashes personal information in LMS as
        defined in EDUCATOR-2802 and sub-tasks.
        """
        params = {'data': {'username': learner['original_username']}}
        with correct_exception():
            return self._client.api.user.v1.accounts.retire_misc.post(**params)

    @_retry_lms_api()
    def retirement_lms_retire(self, learner):
        """
        Deletes, blanks, or one-way hashes all remaining personal information in LMS
        """
        params = {'data': {'username': learner['original_username']}}
        with correct_exception():
            return self._client.api.user.v1.accounts.retire.post(**params)

    @_retry_lms_api()
    def retirement_partner_queue(self, learner):
        """
        Calls LMS to add the given user to the retirement reporting queue
        """
        params = {'data': {'username': learner['original_username']}}
        with correct_exception():
            return self._client.api.user.v1.accounts.retirement_partner_report.put(**params)

    @_retry_lms_api()
    def retirement_partner_report(self):
        """
        Retrieves the list of users to create partner reports for and set their status to
        processing
        """
        with correct_exception():
            return self._client.api.user.v1.accounts.retirement_partner_report.post()

    @_retry_lms_api()
    def retirement_partner_cleanup(self, usernames):
        """
        Removes the given users from the partner reporting queue
        """
        params = {'data': usernames}
        with correct_exception():
            return self._client.api.user.v1.accounts.retirement_partner_report.delete(**params)


class EcommerceApi(BaseApiClient):
    """
    Ecommerce API client with convenience methods for making API calls.
    """
    @_retry_lms_api()
    def retire_learner(self, learner):
        """
        Performs the learner retirement step for Ecommerce
        """
        params = {'data': {'username': learner['original_username']}}
        with correct_exception():
            return self._client.api.v2.user.retire.post(**params)


class CredentialsApi(BaseApiClient):
    """
    Credentials API client with convenience methods for making API calls.
    """
    @_retry_lms_api()
    def retire_learner(self, learner):
        """
        Performs the learner retiement step for Credentials
        """
        params = {'data': {'username': learner['original_username']}}
        with correct_exception():
            return self._client.user.retire.post(**params)
