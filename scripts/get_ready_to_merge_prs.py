#! /usr/bin/env python3

"""
Command-line script to create a release candidate for an application
"""
import io
from os import path
import sys
import logging
import click
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.scripts.github_api import (  # pylint: disable=wrong-import-position
    GitHubAPI
)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command("get_ready_to_merge_prs")
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
def get_ready_to_merge_prs(org,
                             repo,
                             token
                             ):
    """
    Creates a target "release-candidate" branch

    Args:
        org (str):
        repo (str):
        source_branch (str):
        sha (str):
        target_branch (str):
        token (str):
        output_file (str):

    Outputs a yaml file with information about the newly created branch.
    e.g.
     ---
    repo_name: edx-platform
    org_name: edx
    source_branch_name: master
    target_branch_name: release-candidate
    sha: af538da6b229cf1dfa33d0171e75fbff6de4c283
    """
    LOG.info("Getting GitHub token...")
    import pdb;
    pdb.set_trace()

    github_api = GitHubAPI(org, repo, token)

if __name__ == "__main__":
    get_ready_to_merge_prs()  # pylint: disable=no-value-for-parameter
