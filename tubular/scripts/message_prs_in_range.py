#! /usr/bin/env python3

"""
Command-line script message pull requests in a range
"""
from __future__ import absolute_import
from os import path
import sys
import logging
from time import sleep
import click
import yaml


# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.github_api import GitHubAPI  # pylint: disable=wrong-import-position
from github.GithubException import RateLimitExceededException  # pylint: disable=wrong-import-position

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
    u'--base_sha', u'--base-sha',
    help=u'The BASE SHA of the range',
)
@click.option(
    u'--base_ami_tags', u'--base-ami-tags',
    help=u'A YAML file with tags for the base_ami should be used as the baseline for these messages',
    type=click.File(),
)
@click.option(
    u'--ami_tag_app', u'--base-ami-tag-app', 'base_ami_tag_app',
    help=u'The name of the app to read the base_sha from',
)
@click.option(
    u'--head_sha', u'--head-sha',
    help=u'The HEAD SHA of the range',
)
@click.option(
    u'--head-ami-tags',
    help=u'A YAML file with tags for the head_ami should be used as the headline for these messages',
    type=click.File(),
)
@click.option(
    u'--head-ami-tag-app', 'head_ami_tag_app',
    help=u'The name of the app to read the head_sha from',
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
@click.option(
    u'--release_vagrant_broken', u'message_type', flag_value=u'broke_vagrant'
)
@click.option(
    u'--release', u'message_type', type=click.Choice(['stage', 'prod', 'rollback', 'broke_vagrant']),
)
@click.option(
    u'--extra_text', u'extra_text', default=''
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
                          extra_text):
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
        base_ami_tags (str): An open YAML file containing the base AMI tags
        base_ami_tag_app (str): The app name to read the the base_ami_tags
        head_sha (str): The ending SHA
        head_ami_tags (str): Yaml file containing the head AMI tags
        head_ami_tag_app (str): the app name to read the head_ami_tags
        message_type (str): type of message to send
        extra_text (str): Extra text to be inserted in the PR message

    Returns:
        None
    """
    methods = {
        u'stage': u'message_pr_deployed_stage',
        u'prod': u'message_pr_deployed_prod',
        u'rollback': u'message_pr_release_canceled',
        u'broke_vagrant': u'message_pr_broke_vagrant',
    }

    if base_sha is None and base_ami_tags and base_ami_tag_app:
        base_ami_tags = yaml.safe_load(base_ami_tags)
        tag = u'version:{}'.format(base_ami_tag_app)
        version = base_ami_tags[tag]
        _, _, base_sha = version.partition(u' ')

    if head_sha is None and head_ami_tags and head_ami_tag_app:
        head_ami_tags = yaml.safe_load(head_ami_tags)
        tag = u'version:{}'.format(head_ami_tag_app)
        version = head_ami_tags[tag]
        _, _, head_sha = version.partition(u' ')

    api = GitHubAPI(org, repo, token)

    number_of_tries = 10
    time_until_next_try = 2
    pull_requests = []
    while number_of_tries > 0:
        if number_of_tries == 0:
            LOG.error('Was not able to retrieve PR range from GitHub')
            sys.exit(1)
        try:
            LOG.info('Attempting to retrieve PR range')
            pull_requests = api.get_pr_range(base_sha, head_sha)
            LOG.info('Got PR Range')
        except RateLimitExceededException:
            number_of_tries = number_of_tries - 1
            time_until_next_try += time_until_next_try
            LOG.info("Failed to retrieve PR range will try again in {} seconds".format(time_until_next_try))
            sleep(time_until_next_try)
    for pull_request in pull_requests:
        LOG.info(u"Posting message type %r to %d.", message_type, pull_request.number)
        getattr(api, methods[message_type])(pr_number=pull_request, extra_text=extra_text)


if __name__ == u"__main__":
    message_pull_requests()  # pylint: disable=no-value-for-parameter
