#! /usr/bin/env python3

"""
Script to check the combined test status of a GitHub PR or commit SHA.
"""

import io
from os import path
import os
import logging
import sys
import click
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.github_api import GitHubAPI  # pylint: disable=wrong-import-position
from tubular.utils import exactly_one_set  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command("check_tests")
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
    '--out_file',
    help=u"File location in which to write CI test status info.",
    type=click.File(mode='w', lazy=True),
    default=sys.stdout
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
def check_tests(
        org, repo, token, input_file, pr_number, commit_hash,
        out_file, exclude_contexts, include_contexts,
):
    """
    Check the current combined status of a GitHub PR/commit in a repo once.

    If tests have passed for the PR/commit, return a success.
    If any other status besides success (such as in-progress/pending), return a failure.

    If an input YAML file is specified, read the PR number from the file to check.
    If a PR number is specified, check that PR number's tests.
    If a commit hash is specified, check that commit hash's tests.
    """
    # Check for one and only one of the mutually-exclusive params.
    if not exactly_one_set((input_file, pr_number, commit_hash)):
        err_msg = \
            "Exactly one of input_file ({!r}), pr_number ({!r})," \
            " and commit_hash ({!r}) should be specified.".format(
                input_file,
                pr_number,
                commit_hash
            )
        LOG.error(err_msg)
        sys.exit(1)

    gh_utils = GitHubAPI(org, repo, token, exclude_contexts=exclude_contexts, include_contexts=include_contexts)

    status_success = False
    if input_file:
        input_vars = yaml.safe_load(io.open(input_file, 'r'))
        pr_number = input_vars['pr_number']
        combined_status_success, test_statuses = gh_utils.check_combined_status_pull_request(pr_number)
        git_obj = 'PR #{}'.format(pr_number)
    elif pr_number:
        combined_status_success, test_statuses = gh_utils.check_combined_status_pull_request(pr_number)
        git_obj = 'PR #{}'.format(pr_number)
    elif commit_hash:
        combined_status_success, test_statuses = gh_utils.check_combined_status_commit(commit_hash)
        git_obj = 'commit hash {}'.format(commit_hash)

    LOG.info("{}: Combined status of {} is {}.".format(
        sys.argv[0], git_obj, "success" if combined_status_success else "failed"
    ))

    ignore_list = ['GitHub Actions']

    status_success = True

    for test_name, details in test_statuses.items():
        _url, test_status_string = details.split(" ", 1)
        test_status_success = bool(test_status_string == "success")
        if not test_status_success:
            if test_name in ignore_list:
                LOG.info("Ignoring failure of \"{test_name}\" because it is in the ignore list".format(
                    test_name=test_name))
            else:
                LOG.info("Commit failed due to \"{test_name}\": {details}".format(
                    test_name=test_name, details=details))
                status_success = False

    dirname = os.path.dirname(out_file.name)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    yaml.safe_dump(test_statuses, stream=out_file, width=1000)

    # An exit code of 0 means success and non-zero means failure.
    sys.exit(not status_success)


if __name__ == '__main__':
    check_tests()  # pylint: disable=no-value-for-parameter
