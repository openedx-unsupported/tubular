#! /usr/bin/env python3

"""
Command-line script to push the results of a merge of private changes to public back over to the private
repo to keep the repo branches in-sync.
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
    u'--private_org',
    help=u'Org from the private GitHub repository URL of https://github.com/<org>/<repo>',
    default=u'edx'
)
@click.option(
    u'--private_repo',
    help=u'Repo name from the private GitHub repository URL of https://github.com/<org>/<repo>'
)
@click.option(
    u'--private_target_branch',
    help=u'Target branch from the private repo onto which the public source branch will be pushed.',
    required=True
)
@click.option(
    u'--public_org',
    help=u'Org from the public GitHub repository URL of https://github.com/<org>/<repo>',
    default=u'edx'
)
@click.option(
    u'--public_repo',
    help=u'Repo name from the public GitHub repository URL of https://github.com/<org>/<repo>'
)
@click.option(
    u'--public_source_branch',
    help=u'Source branch from the public repo to be pushed onto the target branch of the private repo.',
    required=True
)
@click.option(
    u'--output_file',
    help=u'File in which to write the script\'s YAML output',
)
@click.option(
    u'--reference_repo',
    help=u'Path to a public reference repo to use to speed up cloning.',
)
@click_log.simple_verbosity_option(default=u'INFO')
@click_log.init()
def push_public_to_private(private_org,
                           private_repo,
                           private_target_branch,
                           public_org,
                           public_repo,
                           public_source_branch,
                           output_file,
                           reference_repo):
    u"""
    Push the results of a merge of private changes to public back over to the private
    repo to keep the repo branches in-sync.
    """
    public_github_url = u'git@github.com:{}/{}.git'.format(public_org, public_repo)
    private_github_url = u'git@github.com:{}/{}.git'.format(private_org, private_repo)
    output_yaml = {
        u'private_github_url': private_github_url,
        u'private_target_branch_name': private_target_branch,
        u'public_github_url': public_github_url,
        u'public_target_branch_name': public_source_branch
    }

    # Clone the public repo, checking out the proper public branch.
    LOG.info('Cloning public repo %s with branch %s.', public_github_url, public_source_branch)
    with LocalGitAPI.clone(public_github_url, public_source_branch, reference_repo).cleanup() as local_repo:
        # Add the private repo as a remote for the public git working tree.
        local_repo.add_remote('private', private_github_url)
        try:
            # Push the public branch back to the private branch - without forcing.
            local_repo.push_branch(public_source_branch, 'private', private_target_branch, force=False)
            output_yaml.update({u'branch_pushed': True})
        except Exception as exc:  # pylint: disable=broad-except
            # On any failure besides auth, simply log and ignore.
            # The problem will work itself out in the next private->public cycle.
            LOG.warning(
                "Failed to push public branch %s to private branch %s without fast-forward: %s",
                public_source_branch, private_target_branch, exc
            )
            output_yaml.update({u'branch_pushed': False})

    if output_file:
        with io.open(output_file, u'w') as stream:
            yaml.safe_dump(
                output_yaml,
                stream,
                default_flow_style=False,
                explicit_start=True
            )
    else:
        yaml.safe_dump(
            output_yaml,
            sys.stdout,
        )


if __name__ == u"__main__":
    push_public_to_private()  # pylint: disable=no-value-for-parameter
