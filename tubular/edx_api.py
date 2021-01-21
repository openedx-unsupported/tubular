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


class BaseApiClient:
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
            LOG.error("API Error: {} with status code: {} fetching access token for client: {}".format(
                err.content,
                err.response.status_code,  # pylint: disable=no-member
                client_id,
            ))
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
def correct_exception(log_404_as_error=True):
    """
    Context manager that differentiates 504 gateway timeouts from other 5xx server errors.
    Re-raises any unhandled exceptions.

    Params:
        log_404_as_error (bool): Whether or not to log a response code of 404 as an error. Pass False for
            services like license-manager where 404 is a valid response that represents there was no data for that
            user.
    """
    try:
        yield
    except HttpServerError as err:
        if err.response.status_code == 504:  # pylint: disable=no-member
            # Differentiate gateway errors so different backoff can be used.
            raise EdxGatewayTimeoutError(text_type(err))
        raise err
    except HttpClientError as err:
        status_code = err.response.status_code  # pylint: disable=no-member
        if status_code == 404 and not log_404_as_error:
            # Immediately raise the error so that a 404 isn't logged as an API error in this case.
            raise err

        if hasattr(err, 'content'):
            LOG.error("API Error: {} with status code: {}".format(err.content, status_code))
        else:
            LOG.error("API Error: {} with status code: {} for response without content".format(
                text_type(err),
                status_code,
            ))
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
    def get_learners_by_date_and_status(self, state_to_request, start_date, end_date):
        """
        Retrieves a list of learners in the given retirement state that were
        created in the retirement queue between the dates given. Date range
        is inclusive, so to get one day you would set both dates to that day.

        :param state_to_request: String LMS UserRetirementState state name (ex. COMPLETE)
        :param start_date: Date or Datetime object
        :param end_date: Date or Datetime
        """
        params = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'state': state_to_request
        }
        with correct_exception():
            return self._client.api.user.v1.accounts.retirements_by_status_and_date.get(**params)

    @_retry_lms_api()
    def get_learner_retirement_state(self, username):
        """
        Retrieves the given learner's retirement state.
        """
        with correct_exception():
            return self._client.api.user.v1.accounts(username).retirement_status.get()

    @_retry_lms_api()
    def update_learner_retirement_state(self, username, new_state_name, message, force=False):
        """
        Updates the given learner's retirement state to the retirement state name new_string
        with the additional string information in message (for logging purposes).
        """
        params = {
            'data': {
                'username': username,
                'new_state': new_state_name,
                'response': message
            }
        }

        if force:
            params['data']['force'] = True

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

    # This endpoint additionally returns 500 when the EdxNotes backend service is unavailable.
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
            return self._client.api.user.v1.accounts.retirement_partner_report_cleanup.post(**params)

    @_retry_lms_api()
    def retirement_retire_proctoring_data(self, learner):
        """
        Deletes or hashes learner data from edx-proctoring
        """
        with correct_exception():
            return self._client.api.edx_proctoring.v1.retire_user(learner['user']['id']).post()

    @_retry_lms_api()
    def retirement_retire_proctoring_backend_data(self, learner):
        """
        Removes the given learner from 3rd party proctoring backends
        """
        with correct_exception():
            return self._client.api.edx_proctoring.v1.retire_backend_user(learner['user']['id']).post()

    @_retry_lms_api()
    def bulk_cleanup_retirements(self, usernames):
        """
        Deletes the retirements for all given usernames
        """
        params = {'data': {'usernames': usernames}}
        with correct_exception():
            return self._client.api.user.v1.accounts.retirement_cleanup.post(**params)

    def replace_lms_usernames(self, username_mappings):
        """
        Calls LMS API to replace usernames.
        Param:
            username_mappings: list of dicts where key is current username and value is new desired username
            [{current_un_1: desired_un_1}, {current_un_2: desired_un_2}]
        """
        request_data = {"username_mappings": username_mappings}
        with correct_exception():
            return self._client.api.user.v1.accounts.replace_usernames.post(data=request_data)

    def replace_forums_usernames(self, username_mappings):
        """
        Calls the discussion forums API inside of LMS to replace usernames.
        Param:
            username_mappings: list of dicts where key is current username and value is new unique username
            [{current_un_1: new_un_1}, {current_un_2: new_un_2}]
        """
        request_data = {"username_mappings": username_mappings}
        with correct_exception():
            return self._client.api.discussion.v1.accounts.replace_usernames.post(data=request_data)


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

    @_retry_lms_api()
    def get_tracking_key(self, learner):
        """
        Fetches the ecommerce tracking id used for Segment tracking when
        ecommerce doesn't have access to the LMS user id.
        """
        with correct_exception():
            result = self._client.api.v2.retirement.tracking_id(learner['original_username']).get()
            return result['ecommerce_tracking_id']

    def replace_usernames(self, username_mappings):
        """
        Calls the ecommerce API to replace usernames.
        Param:
            username_mappings: list of dicts where key is current username and value is new unique username
            [{current_un_1: new_un_1}, {current_un_2: new_un_2}]
        """
        request_data = {"username_mappings": username_mappings}
        with correct_exception():
            return self._client.api.v2.user_management.replace_usernames.post(data=request_data)


class CredentialsApi(BaseApiClient):
    """
    Credentials API client with convenience methods for making API calls.
    """
    @_retry_lms_api()
    def retire_learner(self, learner):
        """
        Performs the learner retirement step for Credentials
        """
        params = {'data': {'username': learner['original_username']}}
        with correct_exception():
            return self._client.user.retire.post(**params)

    def replace_usernames(self, username_mappings):
        """
        Calls the credentials API to replace usernames.
        Param:
            username_mappings: list of dicts where key is current username and value is new unique username
            [{current_un_1: new_un_1}, {current_un_2: new_un_2}]
        """
        request_data = {"username_mappings": username_mappings}
        with correct_exception():
            return self._client.api.v2.replace_usernames.post(data=request_data)


class DiscoveryApi(BaseApiClient):
    """
    Discovery API client with convenience methods for making API calls.
    """
    def replace_usernames(self, username_mappings):
        """
        Calls the discovery API to replace usernames.
        Param:
            username_mappings: list of dicts where key is current username and value is new unique username
            [{current_un_1: new_un_1}, {current_un_2: new_un_2}]
        """
        request_data = {"username_mappings": username_mappings}
        with correct_exception():
            return self._client.api.v1.replace_usernames.post(data=request_data)


class DemographicsApi(BaseApiClient):
    """
    Demographics API client.
    """
    @_retry_lms_api()
    def retire_learner(self, learner):
        """
        Performs the learner retirement step for Demographics. Passes the learner's LMS User Id instead of username.
        """
        params = {'data': {'lms_user_id': learner['user']['id']}}
        # If the user we are retiring has no data in the Demographics DB the request will return a 404. We
        # catch the HttpNotFoundError and return True in order to prevent this error getting raised and
        # incorrectly causing the learner to enter an ERROR state during retirement.
        try:
            with correct_exception(log_404_as_error=False):
                return self._client.demographics.api.v1.retire_demographics.post(**params)
        except HttpNotFoundError:
            LOG.info("No demographics data found for user")
            return True


class LicenseManagerApi(BaseApiClient):
    """
    License Manager API client.
    """
    @_retry_lms_api()
    def retire_learner(self, learner):
        """
        Performs the learner retirement step for License manager. Passes the learner's LMS User Id in addition to
        username.
        """
        params = {
            'data': {
                'lms_user_id': learner['user']['id'],
                'original_username': learner['original_username'],
            },
        }
        # If the user we are retiring has no data in the License Manager DB the request will return a 404. We
        # catch the HttpNotFoundError and return True in order to prevent this error getting raised and
        # incorrectly causing the learner to enter an ERROR state during retirement.
        try:
            with correct_exception(log_404_as_error=False):
                return self._client.api.v1.retire_user.post(**params)
        except HttpNotFoundError:
            LOG.info("No license manager data found for user")
            return True
