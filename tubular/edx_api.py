"""
edX API classes which call edX service REST API endpoints using the edx-rest-api-client module.
"""
from edx_rest_api_client.client import EdxRestApiClient


OAUTH_ACCESS_TOKEN_URL = "/oauth2/access_token"


class BaseApiClient(object):
    """
    API client base class used to submit API requests to a particular web service.
    """
    append_slash = True

    def __init__(self, lms_base_url, api_base_url, client_id, client_secret):
        """
        Retrieves OAuth access token from the LMS and creates REST API client instance.
        """
        self.api_base_url = api_base_url
        access_token, __ = self.get_access_token(lms_base_url, client_id, client_secret)
        self._client = EdxRestApiClient(self.api_base_url, jwt=access_token, append_slash=self.append_slash)

    @staticmethod
    def get_access_token(oauth_base_url, client_id, client_secret):
        """
        Returns an access token and expiration date from the OAuth provider.

        Returns:
            (str, datetime)
        """
        return EdxRestApiClient.get_oauth_access_token(
            oauth_base_url + OAUTH_ACCESS_TOKEN_URL, client_id, client_secret, token_type='jwt'
        )


class LmsApi(BaseApiClient):
    """
    LMS API client with convenience methods for making API calls.
    """
    def __init__(self,
                 client_id,
                 client_secret,
                 lms_base_url,
                 api_base_url):
        """
        Inits the LMS API client.
        """
        super(LmsApi, self).__init__(
            lms_base_url, api_base_url, client_id, client_secret
        )

    def learners_to_retire(self, cool_off_days=7):
        """
        Retrieves a list of learners awaiting retirement actions.
        """
        params = {
            'cool_off_days': cool_off_days,
            'states': [
                'PENDING',
                'LOCKING_COMPLETE',
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
        return self._client.api.user.v1.accounts.retirement_queue.get(**params)
