"""
Command-line script to merge a PR.
"""
from __future__ import unicode_literals

from os import path
import sys
import logging
import click
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.github_api import GitHubAPI  # pylint: disable=wrong-import-position
from github.GithubException import GithubException, UnknownObjectException  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command()
@click.option(
    '--org',
    help='Org from the GitHub repository URL of https://github.com/<org>/<repo>',
    default='edx'
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
    default='target/pull_request.yml'
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

    If a PR number is specified, attempts to merge that PR.
    If a PR number is *not* specified -and- an input file is specified, reads the file
    to find the PR ID to merge and attempts to merge that PR.
    """
    github_api = GitHubAPI(org, repo, token)

    if pr_number is None:
        config = yaml.safe_load(open(input_file, 'r'))  # pylint: disable=open-builtin
        pr_number = config['pr_number']

    try:
        github_api.merge_pull_request(pr_number)
    except (GithubException, UnknownObjectException):
        LOG.error("PR #{pr} merge failed. Aborting.".format(pr=pr_number))
        raise

    LOG.info("Merged PR #{pr} successfully.".format(pr=pr_number))


if __name__ == "__main__":
    merge_pull_request()  # pylint: disable=no-value-for-parameter
