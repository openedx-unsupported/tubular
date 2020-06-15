#! /usr/bin/env python3

"""
Command-line script to create a PR to merge a source branch into a target branch.
Both the source and target branches are assumed to already exist.
"""

import io
import logging
import sys
from os import path

import click
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.github_api import GitHubAPI, PullRequestCreationError  # pylint: disable=wrong-import-position

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
    '--token',
    envvar='GIT_TOKEN',
    help='The github access token, see https://help.github.com/articles/creating-an-access-token-for-command-line-use/'
)
@click.option(
    '--source_branch',
    help='Source branch to be merged into the target branch in the PR.',
    required=True
)
@click.option(
    '--target_branch',
    help='Target branch into which the source branch will be merged in the PR.',
    required=True
)
@click.option(
    '--title',
    help='Title to use for the created PR. Auto-generated if not specified.',
    default=None
)
@click.option(
    '--body',
    help='Body to use for the created PR.',
    default=''
)
@click.option(
    '--output_file',
    help="File in which to write the script's YAML output",
    default='target/pull_request.yml'
)
def create_pull_request(org,
                        repo,
                        token,
                        source_branch,
                        target_branch,
                        title,
                        body,
                        output_file):
    """
    Creates a pull request to merge a source branch into a target branch, if needed.
    Both the source and target branches are assumed to already exist. Outputs a YAML
    file with information about the PR creation.
    """
    github_api = GitHubAPI(org, repo, token)

    # First, check to see that there are commits to merge from the source branch to
    # the target branch. If the target branch already contains all the commits from the
    # source branch, then there's no need to create a PR as there's nothing to merge.
    if not github_api.have_branches_diverged(source_branch, target_branch):
        LOG.info(
            "No Pull Request for merging {source} into {target} created - nothing to merge.".format(
                source=source_branch,
                target=target_branch
            )
        )
        output_yaml = {
            'pr_created': False,
        }
    else:
        LOG.info(
            "Creating Pull Request for merging {source} into {target}".format(
                source=source_branch,
                target=target_branch
            )
        )

        if title is None:
            title = "Automated merge of {source} into {target}".format(
                source=source_branch,
                target=target_branch
            )

        try:
            pull_request = github_api.create_pull_request(
                head=source_branch,
                base=target_branch,
                title=title,
                body=body
            )
        except PullRequestCreationError:
            LOG.error("Unable to create pull request. Aborting")
            raise

        output_yaml = {
            'pr_created': True,
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
        }

    with io.open(output_file, 'w') as stream:
        yaml.safe_dump(
            output_yaml,
            stream,
            default_flow_style=False,
            explicit_start=True
        )


if __name__ == "__main__":
    create_pull_request()  # pylint: disable=no-value-for-parameter
