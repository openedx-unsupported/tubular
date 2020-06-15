#! /usr/bin/env python3

"""
Script to check if a PR's base is the specified branch.
"""

import sys
from os import path

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.github_api import GitHubAPI  # pylint: disable=wrong-import-position


@click.command()
@click.option(
    u'--org',
    help=u'Org from the GitHub repository URL of https://github.com/<org>/<repo>',
    default=u'edx'
)
@click.option(
    u'--repo',
    help=u'Repo name from the GitHub repository URL of https://github.com/<org>/<repo>',
    required=True
)
@click.option(
    u'--token',
    envvar=u'GIT_TOKEN',
    help=u'The github access token, see https://help.github.com/articles/creating-an-access-token-for-command-line-use/'
)
@click.option(
    u'--pr_number',
    default=None,
    help=u'Pull request number to check.',
    type=int,
    required=True
)
@click.option(
    u'--branch_name',
    help=u'Branch to check if the base of the PR.',
    required=True
)
def cli(org, repo, token, pr_number, branch_name):
    u"""
    Check if the PR is against the specified branch,
    i.e. if the base of the PR is the specified branch.
    """
    # github.enable_console_debug_logging()
    gh_utils = GitHubAPI(org, repo, token)

    is_base = False
    if pr_number and branch_name:
        is_base = gh_utils.is_branch_base_of_pull_request(pr_number, branch_name)
        print(u"{}: Is branch '{}' the base of PR #{} ? {}!".format(
            sys.argv[0], branch_name, pr_number, u"Yes" if is_base else u"No"
        ))

    # An exit code of 0 means success and non-zero means failure.
    sys.exit(not is_base)


if __name__ == u'__main__':
    cli()  # pylint: disable=no-value-for-parameter
