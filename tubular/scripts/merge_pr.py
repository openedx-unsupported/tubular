#! /usr/bin/env python3

"""
Command-line script to merge a PR.
"""

import io
import logging
import sys
from os import path

import click
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from github.GithubException import GithubException, UnknownObjectException  # pylint: disable=wrong-import-position
from tubular.github_api import GitHubAPI  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command()
@click.option(
    '--org',
    help='Org from the GitHub repository URL of https://github.com/<org>/<repo>',
)
@click.option(
    '--repo',
    help='Repo name from the GitHub repository URL of https://github.com/<org>/<repo>'
)
@click.option(
    '--token',
    envvar='GIT_TOKEN',
    help='The github access token, see https://help.github.com/articles/creating-an-access-token-for-command-line-use/'
)
@click.option(
    '--pr_number',
    default=None,
    help='Pull request number to check.',
    type=int,
)
@click.option(
    '--input_file',
    help='File from which to read the PR information to merge.',
)
def merge_pull_request(org,
                       repo,
                       token,
                       pr_number,
                       input_file):
    """
    Merges a pull request, specified either by number -or read from a YAML file.

    Args:
        org (str):
        repo (str):
        token (str):
        pr_number (int): Number (ID) of PR to merge.
        input_file (str): Path to a YAML file containing PR details.
          The YAML file is expected to have a 'pr_number' field containing the PR number.

    If both or neither PR number and input file are specified, then return a failure.
    If PR number is specified, attempt to merge that PR.
    If input file is specified, attempt to merge the PR number read from the 'pr_number' field.
    """
    github_api = GitHubAPI(org, repo, token)

    if not pr_number and not input_file:
        LOG.error("Neither PR number nor input file were specified - failing.")
        sys.exit(1)
    elif pr_number and input_file:
        LOG.error("Both PR number *and* input file were specified - failing.")
        sys.exit(1)

    if input_file:
        config = yaml.safe_load(io.open(input_file, 'r'))
        if not config['pr_created']:
            # The input file indicates that no PR was created, so no PR tests to check here.
            LOG.info("No PR created - so no PR to merge.")
            sys.exit(0)
        pr_number = config['pr_number']

    try:
        pull_request = github_api.get_pull_request(pr_number)
        if not pull_request.is_merged():
            pull_request.merge()
        else:
            LOG.info("This PR was already merged - no merge is necessary.")
    except (GithubException, UnknownObjectException):
        LOG.error("PR #{pr} merge for org '{org}' & repo '{repo}' failed. Aborting.".format(
            pr=pr_number,
            org=org,
            repo=repo
        ))
        raise

    LOG.info("Merged PR #{pr} for org '{org}' & repo '{repo}' successfully.".format(
        pr=pr_number,
        org=org,
        repo=repo
    ))


if __name__ == "__main__":
    merge_pull_request()  # pylint: disable=no-value-for-parameter
