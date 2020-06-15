#! /usr/bin/env python3

"""
Command-line script to create a tag for a particular SHA.
"""

import datetime
import io
import logging
import sys
from os import path

import click
import yaml
from pytz import timezone

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from github.GithubException import GithubException  # pylint: disable=wrong-import-position
from tubular.github_api import GitHubAPI  # pylint: disable=wrong-import-position
from tubular.utils import exactly_one_set  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)

EST = timezone('US/Eastern')


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
    '--commit_sha',
    help='GitHub repository commit SHA to tag'
)
@click.option(
    '--input_file',
    help='File from which to read the SHA from YAML with key "sha".'
)
@click.option(
    '--branch_name',
    help='Branch name whose HEAD commit SHA will be tagged.',
)
@click.option(
    '--deploy_artifact',
    help='File from which to read the AMI deployment time with key "deploy_time".',
)
@click.option(
    '--tag_name',
    help='Name of the tag to use.',
)
@click.option(
    '--tag_message',
    help='Message to use when tagging.',
)
@click.option(
    '--commit_sha_variable',
    help='Name of the variable to read the SHA from in --input_file',
    default='sha',
)
def create_tag(org,
               repo,
               token,
               commit_sha,
               input_file,
               branch_name,
               deploy_artifact,
               tag_name,
               tag_message,
               commit_sha_variable):
    """
    Creates a tag at a specified commit SHA with a tag name/message.
    The commit SHA is passed in using *one* of these ways:
        - input_file: input YAML file containing a 'sha' key
        - commit_sha: explicitly passed-in commit SHA
        - branch_name: HEAD sha obtained from this branch name
    """
    github_api = GitHubAPI(org, repo, token)

    # Check for one and only one of the mutually-exclusive params.
    if not exactly_one_set((commit_sha, input_file, branch_name)):
        err_msg = \
            "Exactly one of commit_sha ({!r}), input_file ({!r})," \
            " and branch_name ({!r}) should be specified.".format(
                commit_sha,
                input_file,
                branch_name
            )
        LOG.error(err_msg)
        sys.exit(1)

    if input_file:
        input_vars = yaml.safe_load(io.open(input_file, 'r'))
        commit_sha = input_vars[commit_sha_variable]
    elif branch_name:
        commit_sha = github_api.get_head_commit_from_branch_name(branch_name)

    if deploy_artifact:
        deploy_vars = yaml.safe_load(open(deploy_artifact, 'r'))
        deploy_time = datetime.datetime.fromtimestamp(deploy_vars['deploy_time'], EST)
    else:
        # If no deploy artifact was given from which to extract a deploy time, use the current time.
        deploy_time = datetime.datetime.now(EST)
    # If no tag name was given, generate one using the date/time.
    if not tag_name:
        tag_name = 'release-{}'.format(
            deploy_time.strftime("%Y-%m-%d-%H.%M")
        )

    # If no tag message was given, generate one using the date/time.
    if not tag_message:
        tag_message = 'Release for {}'.format(
            deploy_time.strftime("%b %d, %Y %H:%M EST")
        )

    LOG.info(
        "Tagging commit sha {sha} as tag '{tag}' with message '{message}'".format(
            sha=commit_sha,
            tag=tag_name,
            message=tag_message
        )
    )

    try:
        github_api.create_tag(commit_sha, tag_name, tag_message)
    except GithubException:
        LOG.error("Unable to create tag. Aborting")
        raise


if __name__ == "__main__":
    create_tag()  # pylint: disable=no-value-for-parameter
