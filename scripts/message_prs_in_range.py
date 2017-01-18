"""
Command-line script message pull requests in a range
"""
from os import path
import sys
import logging
import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.github_api import GitHubAPI  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command()
@click.option(
    u'--org',
    help=u'Org from the GitHub repository URL of https://github.com/<org>/<repo>',
    default=u'edx'
)
@click.option(
    u'--repo',
    required=True,
    help=u'Repo name from the GitHub repository URL of https://github.com/<org>/<repo>'
)
@click.option(
    u'--token',
    envvar=u'GIT_TOKEN',
    required=True,
    help=u'The github access token, see https://help.github.com/articles/creating-an-access-token-for-command-line-use/'
)
@click.option(
    u'--base_sha',
    required=True,
    help=u'The BASE SHA of the range',
)
@click.option(
    u'--head_sha',
    required=True,
    help=u'The HEAD SHA of the range',
)
@click.option(
    u'--release_stage', u'message_type', flag_value=u'stage'
)
@click.option(
    u'--release_prod', u'message_type', flag_value=u'prod'
)
@click.option(
    u'--release_rollback', u'message_type', flag_value=u'rollback'
)
def message_pull_requests(org,
                          repo,
                          token,
                          base_sha,
                          head_sha,
                          message_type):
    u"""
    Message a range of Pull requests between the BASE and HEAD SHA specified.

    Message can be one of 3 types:
    - PR on stage
    - PR on prod
    - Release canceled

    Args:
        org (str): The github organization
        repo (str): The github repository
        token (str): The authentication token
        base_sha (str): The starting SHA
        head_sha (str): The ending SHA
        message_type (str): type of message to send

    Returns:
        None
    """
    methods = {
        u'stage': u'message_pr_deployed_stage',
        u'prod': u'message_pr_deployed_prod',
        u'rollback': u'message_pr_release_canceled'
    }

    api = GitHubAPI(org, repo, token)
    for pull_request in api.get_pr_range(base_sha, head_sha):
        LOG.info(u"Posting message type %r to %d.", message_type, pull_request.number)
        getattr(api, methods[message_type])(pull_request.number)


if __name__ == u"__main__":
    message_pull_requests()  # pylint: disable=no-value-for-parameter
