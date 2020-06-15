#! /usr/bin/env python3

"""
Command-line script to create a release candidate for an application
"""

import datetime
import io
import logging
import sys
from os import path

import click
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from github.GithubException import GithubException  # pylint: disable=wrong-import-position
from tubular.github_api import (  # pylint: disable=wrong-import-position
    GitHubAPI,
    NoValidCommitsError,
    default_expected_release_date,
    extract_message_summary,
    rc_branch_name_for_date
)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


def valid_date(_, __, date_str):
    """
    Convert a string into a date, for argument parsing.
    """
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        click.BadParameter("Not a valid date: '{0}'.".format(date_str))


EXPECTED_RELEASE_DATE = default_expected_release_date()


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
    '--source_branch',
    help='Source branch whose HEAD is used to create the target branch',
    default='master'
)
@click.option(
    '--target_branch',
    help='Name of the branch to be created',
    default='release-candidate'
)
@click.option(
    '--pr_target_branch',
    help='Name of the branch the pull request will be opened against',
    default='release'
)
@click.option(
    '--release_date',
    help='''
        Specify a date that the release branch is expected to be deployed.
        Should be in YYYY-MM-DD format. If not passed, defaults to the
        next upcoming Tuesday, which is currently {date}.
        '''.format(date=EXPECTED_RELEASE_DATE.isoformat()),
    callback=valid_date,
    envvar='RELEASE_DATE',
    default=EXPECTED_RELEASE_DATE.isoformat()
)
@click.option(
    '--find_commit',
    help='''
        Do not create a branch or a pull request. Only return the commit
        that would be used for the release candidate.
        ''',
    default=False,
    is_flag=True
)
@click.option(
    '--force_commit',
    help='Force the branch to be cut with SHA passed in via this argument.',
    default=None
)
@click.option(
    '--token',
    envvar='GIT_TOKEN',
    help='The github access token, see https://help.github.com/articles/creating-an-access-token-for-command-line-use/'
)
@click.option(
    '--output_file',
    help="File in which to write the script's YAML output",
    default='target/pull_request.yml'
)
def create_release_candidate(org,
                             repo,
                             source_branch,
                             target_branch,
                             pr_target_branch,
                             release_date,
                             find_commit,
                             force_commit,
                             token,
                             output_file):
    """
    Creates a target "release-candidate" branch and pull request

    Args:
        org (str):
        repo (str):
        source_branch (str):
        target_branch (str):
        pr_target_branch (str):
        release_date (str): in the format: YYYY-MM-DD
        find_commit (bool):
        force_commit (str):
        token (str):
        output_file (str):

    Outputs a yaml file with information about the newly created PR.
    e.g.
     ---
    pr_base: 2a800083658e2f5d11d1d40118024f77c59d1b9a
    pr_diff_url: https://github.com/macdiesel412/Rainer/pull/3.diff
    pr_head: af538da6b229cf1dfa33d0171e75fbff6de4c283
    pr_id: 96786312
    pr_number: 3
    pr_mergable: null
    pr_mergable_state: unknown
    pr_repo_url: /repos/macdiesel412/Rainer
    pr_state: open
    pr_url: https://api.github.com/repos/macdiesel412/Rainer/pulls/3

    """
    LOG.info("Getting GitHub token...")
    github_api = GitHubAPI(org, repo, token)

    if force_commit:
        commit_hash = force_commit
        commit_message = "User overide SHA"
    else:
        LOG.info("Fetching commits...")
        try:
            commit = github_api.most_recent_good_commit(source_branch)
            commit_hash = commit.sha
            commit_message = extract_message_summary(commit.commit.message)

        except NoValidCommitsError:
            LOG.error(
                "Couldn't find a recent commit without test failures. Aborting"
            )
            raise

    # Return early if we are only returning the commit hash to stdout
    if find_commit:
        LOG.info(
            "\n\thash: {commit_hash}\n\tcommit message: {message}".format(
                commit_hash=commit_hash,
                message=commit_message
            )
        )
        return

    LOG.info(
        "Branching {rc} off {sha}. ({msg})".format(
            rc=target_branch,
            sha=commit_hash,
            msg=commit_message
        )
    )
    try:
        github_api.delete_branch(target_branch)
    except Exception:  # pylint: disable=broad-except
        LOG.error("Unable to delete branch %s. "
                  "Will attempt to recreate", target_branch)

    try:
        github_api.create_branch(target_branch, commit_hash)
    except Exception:  # pylint: disable=broad-except
        LOG.error("Unable to recreate branch %s. Aborting",
                  target_branch)
        raise

    LOG.info(
        "Creating Pull Request for %s into %s",
        target_branch,
        pr_target_branch
    )

    try:
        pr_title = "Release Candidate {rc}".format(
            rc=rc_branch_name_for_date(release_date.date())
        )
        pull_request = github_api.create_pull_request(
            head=target_branch,
            base=pr_target_branch,
            title=pr_title
        )

        with io.open(output_file, 'w') as stream:
            yaml.safe_dump(
                {
                    'pr_id': pull_request.id,
                    'pr_number': pull_request.number,
                    'pr_url': pull_request.url,
                    'pr_repo_url': github_api.github_repo.url,
                    'pr_head': pull_request.head.sha,
                    'pr_base': pull_request.base.sha,
                    'pr_diff_url': pull_request.diff_url,
                    'pr_mergable': pull_request.mergeable,
                    'pr_state': pull_request.state,
                    'pr_mergable_state': pull_request.mergeable_state,
                },
                stream,
                default_flow_style=False,
                explicit_start=True
            )

    except GithubException:
        LOG.error("Unable to create branch. Aborting")
        raise


if __name__ == "__main__":
    create_release_candidate()  # pylint: disable=no-value-for-parameter
