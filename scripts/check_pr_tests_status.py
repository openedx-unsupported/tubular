"""
Script to check the combined test status of a GitHub PR or commit SHA.
"""
from os import path
import sys
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
)
@click.option(
    u'--commit_hash',
    help=u'Commit hash to check.',
)
def cli(org, repo, token, pr_number, commit_hash):
    u"""
    Check the combined status of a GitHub PR/commit in a repo.

    If tests have passed for the PR/commit, return a success.
    If any other status besides success (such as in-progress/pending), return a failure.
    If both PR number -and- commit hash is specified, return a failure.
    """
    # github.enable_console_debug_logging()
    gh_utils = GitHubAPI(org, repo, token)

    status_success = False
    if pr_number and commit_hash:
        print u"Both PR number and commit hash are specified. Only one of the two should be specified - failing."
        sys.exit(1)
    elif pr_number:
        status_success = gh_utils.check_pull_request_test_status(pr_number)
        print u"{}: Combined status of PR #{} is {}.".format(
            sys.argv[0], pr_number, u"success" if status_success else u"failed"
        )
    elif commit_hash:
        status_success = gh_utils.is_commit_successful(commit_hash)
        print u"{}: Combined status of commit hash {} is {}.".format(
            sys.argv[0], commit_hash, u"success" if status_success else u"failed"
        )

    # An exit code of 0 means success and non-zero means failure.
    sys.exit(not status_success)


if __name__ == u'__main__':
    cli()  # pylint: disable=no-value-for-parameter
