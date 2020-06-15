#! /usr/bin/env python3

"""
Command-line script to create a release candidate for an application
"""

import io
import logging
import sys
from os import path

import click
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.github_api import (  # pylint: disable=wrong-import-position
    GitHubAPI,
    NoValidCommitsError,
    extract_message_summary
)

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
    '--source_branch',
    help='Source branch whose HEAD is used to create the target branch',
)
@click.option(
    '--sha',
    help='SHA to cut the branch from',
)
@click.option(
    '--target_branch',
    help='Name of the branch to be created',
    default='release-candidate'
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
                             sha,
                             target_branch,
                             token,
                             output_file):
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
    if source_branch is not None and sha is not None:
        LOG.error("Please specify either --source_branch or --sha, but not both.")
        sys.exit(1)

    if source_branch is None and sha is None:
        LOG.error("Please specify at least one of --source_branch or --sha.")
        sys.exit(1)

    LOG.info("Getting GitHub token...")
    github_api = GitHubAPI(org, repo, token)

    if sha is None:
        LOG.info("Fetching commits...")
        try:
            commits = github_api.get_commits_by_branch(source_branch)
            commit = commits[0]
            sha = commit.sha
            commit_message = extract_message_summary(commit.commit.message)

        except NoValidCommitsError:
            LOG.error(
                "Couldn't find a recent commit without test failures. Aborting"
            )
            raise

        LOG.info(
            "Branching {rc} off {sha}. ({msg})".format(
                rc=target_branch,
                sha=sha,
                msg=commit_message
            )
        )
    else:
        LOG.info(
            "Branching {rc} off {sha} (explicitly provided).".format(
                rc=target_branch,
                sha=sha,
            )
        )

    try:
        github_api.delete_branch(target_branch)
    except Exception:  # pylint: disable=broad-except
        LOG.error(
            "Unable to delete branch {branch_name}. ".format(branch_name=target_branch)
        )

    try:
        github_api.create_branch(target_branch, sha)
    except Exception:  # pylint: disable=broad-except
        LOG.error("Unable to create branch {branch_name}. Aborting"
                  .format(branch_name=target_branch))
        raise

    with io.open(output_file, 'w') as stream:
        yaml.safe_dump(
            {
                'repo_name': repo,
                'org_name': org,
                'source_branch_name': source_branch,
                'target_branch_name': target_branch,
                'sha': sha,
            },
            stream,
            default_flow_style=False,
            explicit_start=True
        )


if __name__ == "__main__":
    create_release_candidate()  # pylint: disable=no-value-for-parameter
