#! /usr/bin/env python3

"""
Script to check the combined test status of a GitHub PR or commit SHA.
"""

import io
import logging
import sys
from os import path

import click
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.github_api import GitHubAPI  # pylint: disable=wrong-import-position
from tubular.utils import exactly_one_set  # pylint: disable=wrong-import-position

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
    help='Repo name from the GitHub repository URL of https://github.com/<org>/<repo>',
    required=True
)
@click.option(
    '--token',
    envvar='GIT_TOKEN',
    help='The github access token, see https://help.github.com/articles/creating-an-access-token-for-command-line-use/'
)
@click.option(
    '--input_file',
    help='YAML file from which to read a PR number to check, with the top-level key "pr_number"'
)
@click.option(
    '--pr_number',
    default=None,
    help='Pull request number to check.',
    type=int,
)
@click.option(
    '--commit_hash',
    help='Commit hash to check.',
)
@click.option(
    '--exclude-contexts',
    help=u"Regex defining which validation contexts to exclude from this status check.",
    default="datreeio|Renovate|[Cc]odecov|Dependabot"
)
@click.option(
    '--include-contexts',
    help=u"Regex defining which validation contexts to include from this status check.",
    default=None
)
def poll_tests(
        org, repo, token, input_file, pr_number, commit_hash,
        exclude_contexts, include_contexts,
):
    """
    Poll the combined status of a GitHub PR/commit in a repo several times.

    If tests pass for the PR/commit during a poll -or- no PR tests to check, return a success.
    If tests fail for the PR/commit during a poll, return a failure.
    If the maximum polls have occurred -or- a timeout, return a failure.

    If an input YAML file is specified, read the PR number from the file to check.
    Else if both PR number -and- commit hash is specified, return a failure.
    Else if either PR number -or- commit hash is specified, check the tests for the specified value.
    """
    gh_utils = GitHubAPI(org, repo, token, exclude_contexts=exclude_contexts, include_contexts=include_contexts)

    if not exactly_one_set((input_file, pr_number, commit_hash)):
        err_msg = \
            "Exactly one of commit_hash ({!r}), input_file ({!r})," \
            " and pr_number ({!r}) should be specified.".format(
                commit_hash,
                input_file,
                pr_number
            )
        LOG.error(err_msg)
        sys.exit(1)

    if input_file:
        input_vars = yaml.safe_load(io.open(input_file, 'r'))
        if not input_vars['pr_created']:
            # The input file indicates that no PR was created, so no PR tests to check here.
            LOG.info("No PR created - so no PR tests require polling.")
            sys.exit(0)
        pr_number = input_vars['pr_number']
        git_obj = 'PR #{}'.format(pr_number)
        status_success = gh_utils.poll_pull_request_test_status(pr_number)
    elif pr_number:
        git_obj = 'PR #{}'.format(pr_number)
        status_success = gh_utils.poll_pull_request_test_status(pr_number)
    elif commit_hash:
        git_obj = 'commit hash {}'.format(commit_hash)
        status_success = gh_utils.poll_for_commit_successful(commit_hash)

    LOG.info("{cmd}: Combined status of {obj} for org '{org}' & repo '{repo}' is {status}.".format(
        cmd=sys.argv[0],
        obj=git_obj,
        org=org,
        repo=repo,
        status="success" if status_success else "failed"
    ))

    # An exit code of 0 means success and non-zero means failure.
    sys.exit(not status_success)


if __name__ == '__main__':
    poll_tests()  # pylint: disable=no-value-for-parameter
