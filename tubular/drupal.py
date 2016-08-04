import requests
import logging
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
DEPLOY_URL = "{root}/sites/{realm}:{site}/envs/{{env}}/code-deploy.json?path=tags%2F{{tag}}".format(
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
    "acceptance": "edxacc.prod.acquia-sites.com",
    "extra": "edxextra.prod.acquia-sites.com",
}
logger = logging.getLogger(__name__)


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
        logger.error(msg)
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
    VALID_ENVIRONMENTS[env]
    api_client = get_api_client(username, password)
    response = api_client.get(FETCH_TAG_URL.format(env=env))
    response_json = parse_response(response, "Failed to fetch the deployed tag.")
    tag_name = response_json["vcs_path"].replace("tags/", "")
    with open(path_name.format(env=env), "w") as f:
        f.write(tag_name)
    return tag_name


@retry()
def clear_varnish_cache(env, username, password):
    """
    Clears the Varnish cache from a Drupal domain.

    Args:
        env (str): The environment to clear varnish caches in (e.g. test or prod)
        username (str): The Acquia username necessary to run the command.
        password (str): The Acquia password necessary to run the command.

    Returns:
        True if the Varnish cache is successfully cleared.

    Raises:
        KeyError: Raised if env value is invalid.
    """
    api_client = get_api_client(username, password)
    domain = VALID_ENVIRONMENTS[env]
    response = api_client.delete(CLEAR_CACHE_URL.format(env=env, domain=domain))
    response_json = parse_response(response, "Failed to clear cache.")
    return check_state(response_json["id"], username, password)


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
    VALID_ENVIRONMENTS[env]
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
    VALID_ENVIRONMENTS[env]
    api_client = get_api_client(username, password)
    response = api_client.post(BACKUP_DATABASE_URL.format(env=env))
    response_json = parse_response(response, "Failed to backup database.")
    return check_state(response_json["id"], username, password)


@retry(attempts=10, delay_seconds=10, max_time_seconds=100)
def check_state(id, username, password):
    """
    Checks the state of the response to verify it is "done"

    Args:
        id (int): The task id to check the state of.
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
    response = api_client.get(CHECK_TASKS_URL.format(id=id))
    response_json = parse_response(response, "Failed to check state of response.")
    if response_json["state"] == "done":
        return True
    raise BackendError("Check state failed. The state of the response was {state}, not done as expected.".format(
        state=response_json["state"]))
