#! /usr/bin/env python3

"""
Command-line script to push the results of a merge of private changes to public back over to the private
repo to keep the repo branches in-sync.
"""


import io
from os import path
import sys
import logging
import yaml
import click
import click_log

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.git_repo import LocalGitAPI  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command("push_public_to_private")
@click.option(
    '--private_org',
    help='Org from the private GitHub repository URL of https://github.com/<org>/<repo>',
    default='edx'
)
@click.option(
    '--private_repo',
    help='Repo name from the private GitHub repository URL of https://github.com/<org>/<repo>'
)
@click.option(
    '--private_target_branch',
    help='Target branch from the private repo onto which the public source branch will be pushed.',
    required=True
)
@click.option(
    '--public_org',
    help='Org from the public GitHub repository URL of https://github.com/<org>/<repo>',
    default='edx'
)
@click.option(
    '--public_repo',
    help='Repo name from the public GitHub repository URL of https://github.com/<org>/<repo>'
)
@click.option(
    '--public_source_branch',
    help='Source branch from the public repo to be pushed onto the target branch of the private repo.',
    required=True
)
@click.option(
    '--output_file',
    help='File in which to write the script\'s YAML output',
)
@click.option(
    '--reference_repo',
    help='Path to a public reference repo to use to speed up cloning.',
)
@click_log.simple_verbosity_option(default='INFO')
def push_public_to_private(private_org,
                           private_repo,
                           private_target_branch,
                           public_org,
                           public_repo,
                           public_source_branch,
                           output_file,
                           reference_repo):
    """
    Push the results of a merge of private changes to public back over to the private
    repo to keep the repo branches in-sync.
    """
    public_github_url = f'git@github.com:{public_org}/{public_repo}.git'
    private_github_url = f'git@github.com:{private_org}/{private_repo}.git'
    output_yaml = {
        'private_github_url': private_github_url,
        'private_target_branch_name': private_target_branch,
        'public_github_url': public_github_url,
        'public_target_branch_name': public_source_branch
    }

    # Clone the public repo, checking out the proper public branch.
    LOG.info('Cloning public repo %s with branch %s.', public_github_url, public_source_branch)
    with LocalGitAPI.clone(public_github_url, public_source_branch, reference_repo).cleanup() as local_repo:
        # Add the private repo as a remote for the public git working tree.
        local_repo.add_remote('private', private_github_url)
        try:
            # Push the public branch back to the private branch - without forcing.
            local_repo.push_branch(public_source_branch, 'private', private_target_branch, force=False)
            output_yaml.update({'branch_pushed': True})
        except Exception as exc:  # pylint: disable=broad-except
            # On any failure besides auth, simply log and ignore.
            # The problem will work itself out in the next private->public cycle.
            LOG.warning(
                "Failed to push public branch %s to private branch %s without fast-forward: %s",
                public_source_branch, private_target_branch, exc
            )
            output_yaml.update({'branch_pushed': False})

    if output_file:
        with open(output_file, 'w') as stream:
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

if __name__ == "__main__":
    push_public_to_private()  # pylint: disable=no-value-for-parameter
