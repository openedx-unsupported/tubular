"""
edX API classes which call edX service REST API endpoints using the edx-rest-api-client module.
"""
import logging

from slumber.exceptions import HttpClientError

from edx_rest_api_client.client import EdxRestApiClient


LOG = logging.getLogger(__name__)

OAUTH_ACCESS_TOKEN_URL = "/oauth2/access_token"


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


class LmsApi(BaseApiClient):
    """
    LMS API client with convenience methods for making API calls.
    """
    def learners_to_retire(self, cool_off_days=7):
        """
        Retrieves a list of learners awaiting retirement actions.
        """
        params = {
            'cool_off_days': cool_off_days,
            'states': [
                'PENDING',
                'CREDENTIALS_COMPLETE',
                'ECOM_COMPLETE',
                'FORUMS_COMPLETE',
                'EMAIL_LISTS_COMPLETE',
                'ENROLLMENTS_COMPLETE',
                'NOTES_COMPLETE',
                'PARTNERS_NOTIFIED',
                'LMS_COMPLETE',
            ]
        }
        try:
            return self._client.api.user.v1.accounts.retirement_queue.get(**params)
        except HttpClientError as err:
            try:
                LOG.error("API Error: {}".format(err.content))
            except AttributeError:
                LOG.error("API Error: {}".format(str(err)))
            raise err

    def get_learner_retirement_state(self, username):
        """
        Retrieves the given learner's retirement state.
        """
        return self._client.api.user.v1.accounts(username).retirement_status.get()

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

        return self._client.api.user.v1.accounts.update_retirement_status.patch(**params)

    def retirement_deactivate_logout(self, learner):
        """
        Performs the user deactivation and forced logout step of learner retirement
        """
        params = {'data': {'username': learner['original_username']}}
        return self._client.api.user.v1.accounts.deactivate_logout.post(**params)

    def retirement_retire_forum(self, learner):
        """
        Performs the forum retirement step of learner retirement
        """
        params = {'data': {'username': learner['original_username']}}
        return self._client.api.user.v1.accounts.retire_forum.post(**params)

    def retirement_retire_mailings(self, learner):
        """
        Performs the email list retirement step of learner retirement
        """
        params = {'data': {'username': learner['original_username']}}
        return self._client.api.user.v1.accounts.retire_mailings.post(**params)

    def retirement_unenroll(self, learner):
        """
        Unenrolls the user from all courses
        """
        params = {'data': {'username': learner['original_username']}}
        return self._client.api.enrollment.v1.unenroll.post(**params)

    def retirement_lms_retire(self, learner):
        """
        Deletes, blanks, or one-way hashes all remaining personal information in LMS
        """
        params = {'data': {'username': learner['original_username']}}
        return self._client.api.user.v1.accounts.retire.post(**params)


class EcommerceApi(BaseApiClient):
    """
    Ecommerce API client with convenience methods for making API calls.
    """
    def retire_learner(self, learner):
        """
        Performs the learner retirement step for Ecommerce
        """
        params = {'data': {'username': learner['original_username']}}
        return self._client.api.v2.user.retire.post(**params)


class CredentialsApi(BaseApiClient):
    """
    Credentials API client with convenience methods for making API calls.
    """
    def retire_learner(self, learner):
        """
        Performs the learner retiement step for Credentials
        """
        params = {'data': {'username': learner['original_username']}}
        return self._client.user.retire.post(**params)
