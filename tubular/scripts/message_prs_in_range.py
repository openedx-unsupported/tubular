#! /usr/bin/env python3

"""
Command-line script message pull requests in a range
"""

from os import path
import sys
import logging
import click
import yaml
from github.GithubException import UnknownObjectException


# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.github_api import GitHubAPI, MessageType  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command("message_pull_requests")
@click.option(
    '--org',
    help='Org from the GitHub repository URL of https://github.com/<org>/<repo>',
    default='edx'
)
@click.option(
    '--repo',
    required=True,
    help='Repo name from the GitHub repository URL of https://github.com/<org>/<repo>'
)
@click.option(
    '--token',
    envvar='GIT_TOKEN',
    required=True,
    help='The github access token, see https://help.github.com/articles/creating-an-access-token-for-command-line-use/'
)
@click.option(
    '--base_sha', '--base-sha',
    help='The BASE SHA of the range',
)
@click.option(
    '--base_ami_tags', '--base-ami-tags',
    help='A YAML file with tags for the base_ami should be used as the baseline for these messages',
    type=click.File(),
)
@click.option(
    '--ami_tag_app', '--base-ami-tag-app', 'base_ami_tag_app',
    help='The name of the app to read the base_sha from',
)
@click.option(
    '--head_sha', '--head-sha',
    help='The HEAD SHA of the range',
)
@click.option(
    '--head-ami-tags',
    help='A YAML file with tags for the head_ami should be used as the headline for these messages',
    type=click.File(),
)
@click.option(
    '--head-ami-tag-app', 'head_ami_tag_app',
    help='The name of the app to read the head_sha from',
)
@click.option(
    '--release', 'message_type', type=click.Choice(
        sorted([mt.name for mt in MessageType])
    ),
)
@click.option(
    '--extra_text', 'extra_text', default=''
)
@click.option(
    '--no-op',
    help='Disable posting messages for testing',
    is_flag=True
)
def message_pull_requests(org,
                          repo,
                          token,
                          base_sha,
                          base_ami_tags,
                          base_ami_tag_app,
                          head_sha,
                          head_ami_tags,
                          head_ami_tag_app,
                          message_type,
                          extra_text,
                          no_op):
    """
    Message a range of Pull requests between the BASE and HEAD SHA specified.

    Message can be one of several types enumerated in MessageType

    Args:
        org (str): The github organization
        repo (str): The github repository
        token (str): The authentication token
        base_sha (str): The starting SHA
        base_ami_tags (str): An open YAML file containing the base AMI tags
        base_ami_tag_app (str): The app name to read the the base_ami_tags
        head_sha (str): The ending SHA
        head_ami_tags (str): Yaml file containing the head AMI tags
        head_ami_tag_app (str): the app name to read the head_ami_tags
        message_type (str): type of message to send
        extra_text (str): Extra text to be inserted in the PR message
        no_op (bool): Disable posting comments for testing

    Returns:
        None
    """

    if base_sha is None and base_ami_tags and base_ami_tag_app:
        base_ami_tags = yaml.safe_load(base_ami_tags)
        tag = f'version:{base_ami_tag_app}'
        version = base_ami_tags[tag]
        _, _, base_sha = version.partition(' ')

    if head_sha is None and head_ami_tags and head_ami_tag_app:
        head_ami_tags = yaml.safe_load(head_ami_tags)
        tag = f'version:{head_ami_tag_app}'
        version = head_ami_tags[tag]
        _, _, head_sha = version.partition(' ')

    api = get_client(org, repo, token)
    LOG.info(f"Github API Rate Limit: {api.get_rate_limit()}")
    pull_requests = retrieve_pull_requests(api, base_sha, head_sha)
    for pull_request in pull_requests:
        message_pr(api, MessageType[message_type], pull_request, extra_text, no_op)


def get_client(org, repo, token):
    """
    Returns the github client, pointing at the repo specified

    Args:
        org (str): The github organization
        repo (str): The github repository
        token (str): The authentication token

    Returns:
        Returns the github client object
    """
    api = GitHubAPI(org, repo, token)
    return api


def retrieve_pull_requests(api, base_sha, head_sha):
    """
    Use the github API to retrieve pull requests between the BASE and HEAD SHA specified.

    Args:
        api (obj): The github API client
        base_sha (str): The starting SHA
        head_sha (str): The ending SHA

    Returns:
        An array of pull request objects
    """
    LOG.info(f"Github API Rate Limit: {api.get_rate_limit()}")
    try:
        pull_requests = api.get_pr_range(base_sha, head_sha)
    except UnknownObjectException as exc:
        LOG.error("github UnknownObjectException in retrieve_pull_requests(api, base_sha={}, head_sha={})".format(
            base_sha, head_sha))
        raise exc
    return pull_requests


def message_pr(api, message_type, pull_request, extra_text, no_op):
    """
    Send a Message for a Pull request.

    Message can be one of several types enumerated in MessageType

    Args:
        api (obj): The github API client
        message_type (obj): The message type to be sent(see above)
        pull_request (obj): The Pull request for which the message is to be sent
        extra_text (str): extra text to include in the message

    Returns:
        None
    """
    LOG.info(f"Github API Rate Limit: {api.get_rate_limit()}")
    if no_op:
        LOG.info("No-op mode: Whould have posted message type %r to %d.", message_type.name, pull_request.number)
    else:
        LOG.info("Posting message type %r to %d.", message_type.name, pull_request.number)

        try:
            api.message_pr_with_type(pr_number=pull_request, message_type=message_type, extra_text=extra_text)
        except UnknownObjectException as exc:
            LOG.error("message_pr_with_type args were: pr_number={} message_type={} extra_text={}".format(
                pull_request, message_type, extra_text))
            raise exc


if __name__ == "__main__":
    message_pull_requests()  # pylint: disable=no-value-for-parameter
