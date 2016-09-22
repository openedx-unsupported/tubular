"""
Script to check if a PR's base is the specified branch.
"""
from __future__ import unicode_literals

import os
import sys
import click
from github_api_utils import GitHubApiUtils, EDX_PLATFORM_REPO_ID  # pylint: disable=relative-import


@click.command()
@click.option(
    '--repo_id', '-r',
    default=EDX_PLATFORM_REPO_ID,
    help="ID for the GitHub repository (defaults to edx-platform's ID).",
    required=False
)
@click.option(
    '--pr_number', '-p',
    default=None,
    help="Pull request number to check.",
    type=int,
)
@click.option(
    '--pr_env_var',
    help="Name of environment variable containing pull request number to check.",
)
@click.option(
    '--branch_name', '-b',
    help="Branch to check if the base of the PR.",
)
@click.option(
    '--branch_env_var',
    help="Name of environment variable containing branch to check if the base of the PR.",
)
def cli(repo_id, pr_number, pr_env_var, branch_name, branch_env_var):
    """
    Check if the PR is against the specified branch,
    i.e. if the base of the PR is the specified branch.
    """
    # github.enable_console_debug_logging()
    gh_utils = GitHubApiUtils(repo_id)

    if pr_number is None:
        if pr_env_var:
            pr_number = int(os.environ[pr_env_var])
    if branch_name is None:
        if branch_env_var:
            branch_name = os.environ[branch_env_var]

    is_base = False
    if pr_number and branch_name:
        is_base = gh_utils.is_branch_base_of_pr(pr_number, branch_name)
        print "{}: Is branch '{}' the base of PR #{} ? {}!".format(
            sys.argv[0], branch_name, pr_number, "Yes" if is_base else "No"
        )

    # An exit code of 0 means success and non-zero means failure.
    sys.exit(not is_base)


if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter
