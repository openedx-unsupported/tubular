"""
Methods to interact with the Drupal API to perform various tasks.
"""

import io
import logging
import json
import requests
from tubular.utils.retry import retry
from tubular.exception import BackendError


ACQUIA_ENDPOINT = "https://cloud.acquia.com/api"
DATABASE = "edx"

TOKEN_URL = "https://accounts.acquia.com/api/auth/oauth/token"
FETCH_ENV_URL = "{root}/applications/{{applicationUuid}}/environments".format(
    root=ACQUIA_ENDPOINT
)
FETCH_TAG_URL = "{root}/environments/{{environmentId}}".format(
    root=ACQUIA_ENDPOINT
)
CLEAR_CACHE_URL = "{root}/environments/{{environmentId}}/domains/{{domain}}/actions/clear-varnish".format(
    root=ACQUIA_ENDPOINT
)
DEPLOY_URL = "{root}/environments/{{environmentId}}/code/actions/switch".format(
    root=ACQUIA_ENDPOINT
)
BACKUP_DATABASE_URL = "{root}/environments/{{environmentId}}/databases/{{databaseName}}/backups".format(
    root=ACQUIA_ENDPOINT
)

# Maps environments to domains.
VALID_ENVIRONMENTS = {
    "acceptance": [
        "edxacc.prod.acquia-sites.com",
        "acceptance-edx-mktg-backend.edx.org",
        "acceptance-edx-mktg-edit.edx.org",
        "acceptance-edx-mktg-webview.edx.org",
        "acceptance.edx.org",
    ],
    "dev": [
        "edxdev.prod.acquia-sites.com",
        "dev-edx-mktg-backend.edx.org",
        "dev-edx-mktg-edx.edx.org",
        "dev-edx-mktg-webview.edx.org",
        "dev.edx.org",
        "www.dev.edx.org",
    ],
    "extra": [
        "edxextra.prod.acquia-sites.com",
        "extra-edx-mktg-backend.edx.org",
        "extra-edx-mktg-edit.edx.org",
        "extra-webview.edx.org",
        "extra.edx.org",
    ],
    "prod": [
        "edx.prod.acquia-sites.com",
        "prod-edx-mktg-backend.edx.org",
        "prod-edx-mktg-edit.edx.org",
        "webview.edx.org",
        "www.edx.org",
    ],
    "qa": [
        "edxqa.prod.acquia-sites.com",
        "qa-edx-mktg-backend.edx.org",
        "qa-edx-mktg-edit.edx.org",
        "qa-edx-mktg-webview.edx.org",
        "qa.edx.org",
    ],
    "test": [
        "edxstg.prod.acquia-sites.com",
        "stage-edx-mktg-backend.edx.org",
        "stage-edx-mktg-edit.edx.org",
        "stage-webview.edx.org",
        "stage.edx.org",
        "www.stage.edx.org",
    ],
}
LOG = logging.getLogger(__name__)


def get_api_token(client_id, client_secret):
    """
    Get api token from Acquia to be used for future calls.

    Args:
        client_id (str): The client id generated via Acquia
        password (str): The secret key generated via Acquia

    Returns:
        The access token
    """

    data = {'grant_type': 'client_credentials'}
    access_token_response = requests.post(TOKEN_URL,
                                          data=data,
                                          verify=False,
                                          allow_redirects=False,
                                          auth=(client_id, client_secret))

    tokens = json.loads(access_token_response.text)
    return tokens['access_token']


def parse_response(response, error_message):
    """
    Parses the response.

    Args:
        response (requests.Response):
        error_message (str):

    Returns:
        The JSON representation of the response if no errors.

    Raises:
        BackendError: Raised if the response's status code is not 200 or 202.
    """
    if response.status_code != 200 and response.status_code != 202:
        msg = "{specific}\nStatus Code: {status}\nBody: {body}".format(specific=error_message,
                                                                       status=response.status_code, body=response.text)
        LOG.error(msg)
        raise BackendError(msg)
    return response.json()


def get_acquia_v2(url, access_token):
    """
    Perform get request to Acquia v2 end point.

    Args:
        url (str): Acquia v2 end point.
        access_token (str): token to authenticate client

    Returns:
        The Response object.
    """
    api_call_headers = {'Authorization': 'Bearer ' + access_token}
    api_call_response = requests.get(url, headers=api_call_headers, verify=False)

    return api_call_response


def post_acquia_v2(url, access_token, body=None):
    """
    Perform post request to Acquia v2 end point.

    Args:
        url (str): Acquia v2 end point.
        access_token (str): token to authenticate client
        body (dict): json data to be send to end point

    Returns:
        The Response object.
    """

    api_call_headers = {'Authorization': 'Bearer ' + access_token}
    api_call_response = requests.post(url, headers=api_call_headers, json=body, verify=False)
    return api_call_response


def fetch_environment_uid(app_id, env, token):
    """
    Fetches environment uid based on environment name

    Args:
        app_id (str): Application id assigned to Drupal instance.
        env (str): The environment to clear varnish caches in (e.g. test or prod)
        token (str): token to authenticate client

    Returns:
        environment id (str): The identifier is a key consisting of the internal database ID
        of the environment and the application UUID

    Raises:
        KeyError: Raised if env value is invalid.
    """
    response = get_acquia_v2(FETCH_ENV_URL.format(applicationUuid=app_id), token)
    response_json = parse_response(response, "Failed to get environment detail.")
    envs = response_json["_embedded"]["items"]

    environment_id = None
    for e in envs:
        if e['name'] == env:
            environment_id = e['id']
            break

    return environment_id


@retry()
def fetch_deployed_tag(app_id, env, client_id, secret, path_name):
    """
    Fetches the currently deployed tag in the given environment

    Args:
        app_id (str): Application id assigned to Drupal instance.
        env (str): The environment to clear varnish caches in (e.g. test or prod)
        client_id (str): The Acquia api client id necessary to run the command.
        secret (str): The Acquia api secret key to run the command.
        path_name (str): The path to write the tag name to.

    Returns:
        tag_name (str): The name of the tag deployed in the environment.

    Raises:
        KeyError: Raised if env value is invalid.
    """
    __ = VALID_ENVIRONMENTS[env]

    token = get_api_token(client_id, secret)
    environmentId = fetch_environment_uid(app_id, env, token)
    if environmentId:
        response = get_acquia_v2(FETCH_TAG_URL.format(environmentId=environmentId), token)
        response_json = parse_response(response, "Failed to fetch the deployed tag.")
        tag_name = response_json["vcs"]["path"]
        with io.open(path_name.format(env=env), "w") as f:
            f.write(tag_name)
        return tag_name


@retry()
def clear_varnish_cache(app_id, env, client_id, secret):
    """
    Clears the Varnish cache from all domains in a Drupal environment.

    Args:
        app_id (str): Application id assigned to Drupal instance.
        env (str): The environment to clear varnish caches in (e.g. test or prod)
        client_id (str): The Acquia api client id necessary to run the command.
        secret (str): The Acquia api secret key to run the command.

    Returns:
        True if all of the Varnish caches are successfully cleared.

    Raises:
        KeyError: Raised if env value is invalid.
        BackendError: Raised if the varnish cache fails to clear in any of the domains.
    """
    domains = VALID_ENVIRONMENTS[env]
    failure = ""

    token = get_api_token(client_id, secret)
    environmentId = fetch_environment_uid(app_id, env, token)
    if environmentId:
        for domain in domains:
            response = post_acquia_v2(CLEAR_CACHE_URL.format(environmentId=environmentId, domain=domain), token)
            error_message = "Failed to clear cache in {domain}.".format(domain=domain)
            try:
                response_json = parse_response(response, error_message)
            except BackendError:
                failure = failure + error_message + "\n"
                continue
            check_state(response_json['_links']['notification']['href'], token)
        if failure:
            raise BackendError(failure)
        return True


@retry()
def deploy(app_id, env, client_id, secret, branch_or_tag):
    """
    Deploys a given branch or tag to the specified environment.

    Args:
        app_id (str): Application id assigned to Drupal instance.
        env (str): The environment to deploy code in (e.g. test or prod)
        client_id (str): The Acquia api client id necessary to run the command.
        secret (str): The Acquia api secret key to run the command.
        branch_or_tag (str): The branch or tag to deploy to the specified environment.

    Returns:
        True if the code is successfully deployed.

    Raises:
        KeyError: Raised if env value is invalid.
    """
    __ = VALID_ENVIRONMENTS[env]
    token = get_api_token(client_id, secret)
    environmentId = fetch_environment_uid(app_id, env, token)
    if environmentId:
        body = {"branch": branch_or_tag}
        response = post_acquia_v2(DEPLOY_URL.format(environmentId=environmentId), token, body)
        response_json = parse_response(response, "Failed to deploy code.")
        return check_state(response_json['_links']['notification']['href'], token)


@retry()
def backup_database(app_id, env, client_id, secret):
    """
    Creates a backup of the database in the specified environment.

    Args:
        app_id (str): Application id assigned to our Drupal instance.
        env (str): The environment the database backup will take place in (e.g. test or prod)
        client_id (str): The Acquia api client id necessary to run the command.
        secret (str): The Acquia api secret key to run the command.

    Returns:
        True if a database backup is successfully created.

    Raises:
        KeyError: Raised if env value is invalid.
    """
    __ = VALID_ENVIRONMENTS[env]
    token = get_api_token(client_id, secret)
    environmentId = fetch_environment_uid(app_id, env, token)
    if environmentId:
        response = post_acquia_v2(BACKUP_DATABASE_URL.format(environmentId=environmentId, databaseName=DATABASE), token)
        response_json = parse_response(response, "Failed to backup database.")
        return check_state(response_json['_links']['notification']['href'], token)


@retry(attempts=30, delay_seconds=10, max_time_seconds=300)
def check_state(notification_url, token):
    """
    Checks the status of the response to verify it is "done"

    Args:
        notification_url (str): The notification url to use to check the state of.
        token (str): token to authenticate client

    Returns:
        True if status of the response is "completed"

    Raises:
        BackendError: Raised so the method will retry since immediately after receiving the
            response, the status will still be "in-progress". Can"t rely on parse_response since
            the response should return a 200, just not the status wanted.
    """
    response = get_acquia_v2(notification_url, token)
    response_json = parse_response(response, "Failed to check state of response.")
    if response_json["status"] == "completed":
        return True
    raise BackendError("Check status failed. The status of the response was {status}, not done as expected.\n"
                       "JSON Data: {response}".format(status=response_json["status"], response=response_json))
