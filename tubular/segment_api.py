"""
Segment API call wrappers
"""
import logging

import backoff
import requests
from six import text_type


# These are the keys in the learner dict that contain IDs we need to retire from Segment
IDENTIFYING_KEYS = ['id', 'original_username', 'ecommerce_segment_id']

# The Segment GraphQL mutation for authorization
AUTH_MUTATION = "mutation auth($email:String!, $password:String!) {login(email:$email, password:$password)}"

# The Segment GraphQL mutation for SUPPRESS_AND_DELETE for a particular workspace and source
SUPPRESS_MUTATION = """
mutation {{
  createSourceRegulation(
    workspaceSlug: "{}"
    sourceSlug: "{}"
    type: SUPPRESS_AND_DELETE
    userId: "{}"
  ) {{
    id
  }}
}}"""

LOG = logging.getLogger(__name__)


def _backoff_handler(details):
    """
    Simple logging handler for when timeout backoff occurs.
    """
    LOG.info('Trying again in {wait:0.1f} seconds after {tries} tries calling {target}'.format(**details))


def _wait_30_seconds():
    """
    Backoff generator that waits for 30 seconds.
    """
    return backoff.constant(interval=30)


def _exception_not_internal_svr_error(exc):
    """
    Giveup method that gives up backoff upon any non-5xx and 504 server errors.
    """
    return not 500 <= exc.response.status_code < 600


def _retry_segment_api():
    """
    Decorator which enables retries with sane backoff defaults
    """
    def inner(func):  # pylint: disable=missing-docstring
        func_with_backoff = backoff.on_exception(
            backoff.expo,
            requests.exceptions.HTTPError,
            max_time=90,  # in seconds
            giveup=_exception_not_internal_svr_error,
            on_backoff=lambda details: _backoff_handler(details)  # pylint: disable=unnecessary-lambda
        )
        func_with_timeout_backoff = backoff.on_exception(
            _wait_30_seconds,
            requests.exceptions.Timeout,
            max_tries=4,
            on_backoff=lambda details: _backoff_handler(details)  # pylint: disable=unnecessary-lambda
        )
        return func_with_backoff(func_with_timeout_backoff(func))
    return inner


class SegmentApi(object):
    """
    Segment API client with convenience methods
    """
    def __init__(self, base_url, auth_email, auth_password, projects_to_retire, workspace_slug):
        self.base_url = base_url
        self.auth_email = auth_email
        self.auth_password = auth_password
        self.projects_to_retire = projects_to_retire
        self.workspace_slug = workspace_slug

    def _get_auth_token(self):
        """
        Makes the request to get an auth token and return it
        """
        mutation = {
            'query': AUTH_MUTATION,
            'variables':
                {
                    "email": "{email}".format(email=self.auth_email),
                    "password": "{password}".format(password=self.auth_password)
                }
        }

        resp = None
        resp_json = None
        try:
            resp = requests.post(self.base_url, json=mutation)
            resp_json = resp.json()
            return resp_json['data']['login']['access_token']
        except (TypeError, KeyError):
            LOG.error('Error occurred getting access token. Response {}'.format(text_type(resp)))
            LOG.error('Response JSON: {}'.format(text_type(resp_json)))
            raise

    @_retry_segment_api()
    def _call_suppress_and_delete(self, mutation):
        """
        Actually makes the Segment GraphQL SUPPRESS_AND_DELETE call

        5xx errors and timeouts will be retried via _retry_segment_api,
        all others will bubble up.

        We get the access token here instead of setting it up ahead of time
        or in __init__ because these tokens seem to be very short-lived. If a
        previous retirement step runs long, or if there are numerous retries,
        the token might time out.
        """
        access_token = self._get_auth_token()
        headers = {"Authorization": "Bearer {}".format(access_token)}
        return requests.post(self.base_url, json=mutation, headers=headers)

    def suppress_and_delete(self, learner):
        """
        Sets up the Segment GraphQL calls to GDPR forget a user.

        Due to the way we use Segment we need to make one call per "source" for
        each different identifier associated with the user. We have identified
        3 identifiers that might be tied to a user in production - LMS user id,
        Ecommerce user id, and username (deprecated), and currently have 12
        production projects that identify users. So it's possible this will make
        36 Segment calls.

        :param learner: The learner dict returned from LMS, should contain all
            we need to retire this learner.
        """
        for project in self.projects_to_retire:
            for id_key in IDENTIFYING_KEYS:
                if learner[id_key] is None:
                    LOG.info('Identifying key {} is None, learner may have no Ecommerce ID. Skipping.')
                    continue

                mutation = {
                    'query': SUPPRESS_MUTATION.format(self.workspace_slug, project, learner[id_key])
                }

                resp = self._call_suppress_and_delete(mutation)
                resp_json = resp.json()

                try:
                    supression_id = resp_json['data']['createWorkspaceRegulation']['id']
                    print('Suppress and delete queued. Id: {}'.format(supression_id))
                except (TypeError, KeyError):
                    # This message means the identifier has already been submitted
                    # for this project, we count this as success.
                    if 'Regulation already exists' in resp_json['errors'][0]['message']:
                        LOG.info(resp_json['errors'][0]['message'])
                    else:
                        LOG.error('Errors were encountered for learner id {} key {}: {}'.format(
                            learner['id'],
                            id_key,
                            text_type(resp_json)
                        ))
                        raise
