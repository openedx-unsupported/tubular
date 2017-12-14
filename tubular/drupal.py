"""
Methods to interact with the Drupal API to perform various tasks.
"""
from __future__ import absolute_import
from __future__ import unicode_literals

import io
import logging
import requests
from requests.auth import HTTPBasicAuth
from tubular.utils.retry import retry
from tubular.exception import BackendError


ACQUIA_ENDPOINT = "https://cloudapi.acquia.com/v1"
REALM = "prod"
SITE = "edx"
DATABASE = "edx"
FETCH_TAG_URL = "{root}/sites/{realm}:{site}/envs/{{env}}.json".format(
    root=ACQUIA_ENDPOINT, realm=REALM, site=SITE
)
CLEAR_CACHE_URL = "{root}/sites/{realm}:{site}/envs/{{env}}/domains/{{domain}}/cache.json".format(
    root=ACQUIA_ENDPOINT, realm=REALM, site=SITE
)
DEPLOY_URL = "{root}/sites/{realm}:{site}/envs/{{env}}/code-deploy.json?path={{tag}}".format(
    root=ACQUIA_ENDPOINT, realm=REALM, site=SITE
)
BACKUP_DATABASE_URL = "{root}/sites/{realm}:{site}/envs/{{env}}/dbs/{database}/backups.json".format(
    root=ACQUIA_ENDPOINT, realm=REALM, site=SITE, database=DATABASE
)
CHECK_TASKS_URL = "{root}/sites/{realm}:{site}/tasks/{{id}}.json".format(
    root=ACQUIA_ENDPOINT, realm=REALM, site=SITE
)
# Maps environments to domains.
VALID_ENVIRONMENTS = {
    "test": [
        "edxstg.prod.acquia-sites.com",
        "stage-edx-mktg-backend.edx.org",
        "stage-edx-mktg-edit.edx.org",
        "stage-webview.edx.org",
        "stage.edx.org",
        "www.stage.edx.org",
    ],
    "prod": [
        "edx.prod.acquia-sites.com",
        "prod-edx-mktg-backend.edx.org",
        "prod-edx-mktg-edit.edx.org",
        "webview.edx.org",
        "www.edx.org",
    ],
}
LOG = logging.getLogger(__name__)


def get_api_client(username, password):
    """
    Creates an API Client and authenticates the client.

    Args:
        username (str): The username used to authenticate the client
        password (str): The password used to authenticate the client

    Returns:
        The authenticated API Client
    """
    api_client = requests.Session()
    api_client.auth = HTTPBasicAuth(username, password)
    return api_client


def parse_response(response, error_message):
    """
    Parses the response.

    Args:
        response (requests.Response):
        error_message (str):

    Returns:
        The JSON representation of the response if no errors.

    Raises:
        BackendError: Raised if the response's status code is not 200.
    """
    if response.status_code != 200:
        msg = "{specific}\nStatus Code: {status}\nBody: {body}".format(specific=error_message,
                                                                       status=response.status_code, body=response.text)
        LOG.error(msg)
        raise BackendError(msg)
    return response.json()


@retry()
def fetch_deployed_tag(env, username, password, path_name):
    """
    Fetches the currently deployed tag in the given environment

    Args:
        env (str): The environment to clear varnish caches in (e.g. test or prod)
        username (str): The Acquia username necessary to run the command.
        password (str): The Acquia password necessary to run the command.
        path_name (str): The path to write the tag name to.

    Returns:
        tag_name (str): The name of the tag deployed in the environment.

    Raises:
        KeyError: Raised if env value is invalid.
    """
    __ = VALID_ENVIRONMENTS[env]
    api_client = get_api_client(username, password)
    response = api_client.get(FETCH_TAG_URL.format(env=env))
    response_json = parse_response(response, "Failed to fetch the deployed tag.")
    tag_name = response_json["vcs_path"]
    with io.open(path_name.format(env=env), "w") as f:
        f.write(tag_name)
    return tag_name


@retry()
def clear_varnish_cache(env, username, password):
    """
    Clears the Varnish cache from all domains in a Drupal environment.

    Args:
        env (str): The environment to clear varnish caches in (e.g. test or prod)
        username (str): The Acquia username necessary to run the command.
        password (str): The Acquia password necessary to run the command.

    Returns:
        True if all of the Varnish caches are successfully cleared.

    Raises:
        KeyError: Raised if env value is invalid.
        BackendError: Raised if the varnish cache fails to clear in any of the domains.
    """
    api_client = get_api_client(username, password)
    domains = VALID_ENVIRONMENTS[env]
    failure = ""
    for domain in domains:
        response = api_client.delete(CLEAR_CACHE_URL.format(env=env, domain=domain))
        error_message = "Failed to clear cache in {domain}.".format(domain=domain)
        try:
            response_json = parse_response(response, error_message)
        except BackendError:
            failure = failure + error_message + "\n"
            continue
        check_state(response_json["id"], username, password)
    if failure:
        raise BackendError(failure)
    return True


@retry()
def deploy(env, username, password, tag):
    """
    Deploys a given tag to the specified environment.

    Args:
        env (str): The environment to deploy code in (e.g. test or prod)
        username (str): The Acquia username necessary to run the command.
        password (str): The Acquia password necessary to run the command.
        tag (str): The tag to deploy to the specified environment.

    Returns:
        True if the code is successfully deployed.

    Raises:
        KeyError: Raised if env value is invalid.
    """
    __ = VALID_ENVIRONMENTS[env]
    api_client = get_api_client(username, password)
    response = api_client.post(DEPLOY_URL.format(env=env, tag=tag))
    response_json = parse_response(response, "Failed to deploy code.")
    return check_state(response_json["id"], username, password)


@retry()
def backup_database(env, username, password):
    """
    Creates a backup of the database in the specified environment.

    Args:
        env (str): The environment the database backup will take place in (e.g. test or prod)
        username (str): The Acquia username necessary to run the command.
        password (str): The Acquia password necessary to run the command.

    Returns:
        True if a database backup is successfully created.

    Raises:
        KeyError: Raised if env value is invalid.
    """
    __ = VALID_ENVIRONMENTS[env]
    api_client = get_api_client(username, password)
    response = api_client.post(BACKUP_DATABASE_URL.format(env=env))
    response_json = parse_response(response, "Failed to backup database.")
    return check_state(response_json["id"], username, password)


@retry(attempts=30, delay_seconds=10, max_time_seconds=300)
def check_state(task_id, username, password):
    """
    Checks the state of the response to verify it is "done"

    Args:
        task_id (int): The task id to check the state of.
        username (str): The Acquia username necessary to run the command.
        password (str): The Acquia password necessary to run the command.

    Returns:
        True if state of the response is "done"

    Raises:
        BackendError: Raised so the method will retry since immediately after receiving the
            response, the state will still be "waiting". Can"t rely on parse_response since
            the response should return a 200, just not the state wanted.
    """
    api_client = get_api_client(username, password)
    response = api_client.get(CHECK_TASKS_URL.format(id=task_id))
    response_json = parse_response(response, "Failed to check state of response.")
    if response_json["state"] == "done":
        return True
    raise BackendError("Check state failed. The state of the response was {state}, not done as expected.\n"
                       "JSON Data: {response}".format(state=response_json["state"], response=response_json))
