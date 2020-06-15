#! /usr/bin/env python3

"""
Command-line script to merge a branch.
"""

import io
import logging
import sys
from os import path

import click
import click_log
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.git_repo import LocalGitAPI  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command()
@click.option(
    u'--org',
    help=u'Org from the GitHub repository URL of https://github.com/<org>/<repo>',
    default=u'edx'
)
@click.option(
    u'--repo',
    help=u'Repo name from the GitHub repository URL of https://github.com/<org>/<repo>'
)
@click.option(
    u'--source_branch',
    help=u'Source branch to be merged into the target branch in the PR.',
    required=True
)
@click.option(
    u'--target_branch',
    help=u'Target branch into which the source branch will be merged in the PR.',
    required=True
)
@click.option(
    u'--fast_forward_only',
    help=u'Either perform a fast-forward merge -or- fail if not possible.',
    default=False,
    is_flag=True
)
@click.option(
    u'--output_file',
    help=u'File in which to write the script\'s YAML output',
    default=u'target/merge_branch_sha.yml'
)
@click.option(
    u'--reference-repo',
    help=u'Path to a reference repo to use to speed up cloning',
)
@click_log.simple_verbosity_option(default=u'INFO')
@click_log.init()
def merge_branch(org,
                 repo,
                 source_branch,
                 target_branch,
                 fast_forward_only,
                 output_file,
                 reference_repo):
    u"""
    Merges the source branch into the target branch without creating a pull request for the merge.
    Clones the repo in order to perform the proper git commands locally.

    Args:
        org (str):
        repo (str):
        source_branch (str):
        target_branch (str):
        fast_forward_only (bool): If True, the branch merge will be performed as a fast-forward merge.
          If the merge cannot be performed as a fast-forward merge, the merge will fail.
    """
    github_url = u'git@github.com:{}/{}.git'.format(org, repo)
    with LocalGitAPI.clone(github_url, target_branch, reference_repo).cleanup() as local_repo:
        merge_sha = local_repo.merge_branch(source_branch, target_branch, fast_forward_only)
        local_repo.push_branch(target_branch)

    with io.open(output_file, u'w') as stream:
        yaml.safe_dump(
            {
                u'org_name': org,
                u'repo_name': repo,
                u'source_branch_name': source_branch,
                u'target_branch_name': target_branch,
                u'fast_forward_only': fast_forward_only,
                u'sha': merge_sha
            },
            stream,
            default_flow_style=False,
            explicit_start=True
        )


if __name__ == u"__main__":
    merge_branch()  # pylint: disable=no-value-for-parameter
