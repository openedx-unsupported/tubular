"""
Command-line script to create a PR to merge a source branch into a target branch.
Both the source and target branches are assumed to already exist.
"""
from __future__ import unicode_literals

from os import path
import sys
import logging
import click
import yaml


# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.github_api import GitHubAPI  # pylint: disable=wrong-import-position
from github.GithubException import GithubException  # pylint: disable=wrong-import-position

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
    Creates a pull request to merge a source branch into a target branch.
    Both the source and target branches are assumed to already exist.

    Args:
        org (str):
        repo (str):
        token (str):
        source_branch (str):
        target_branch (str):
        title (str):
        body (str):
        output_file (str):

    Outputs a yaml file with information about the newly created PR.
    e.g.
     ---
    pr_id: 96786312
    pr_number: 3
    pr_url: https://api.github.com/repos/macdiesel412/Rainer/pulls/3
    pr_repo_url: /repos/macdiesel412/Rainer
    pr_head: af538da6b229cf1dfa33d0171e75fbff6de4c283
    pr_base: 2a800083658e2f5d11d1d40118024f77c59d1b9a
    pr_diff_url: https://github.com/macdiesel412/Rainer/pull/3.diff
    pr_mergable: null
    pr_state: open
    pr_mergable_state: unknown
    """
    LOG.info("Getting GitHub token...")
    github_api = GitHubAPI(org, repo, token)

    LOG.info(
        "Creating Pull Request for merging {source} into {target}".format(
            source=source_branch,
            target=target_branch
        )
    )

    try:
        if title is None:
            title = "Automated merge of {source} into {target}" .format(
                source=source_branch,
                target=target_branch
            )
        pull_request = github_api.create_pull_request(
            head=source_branch,
            base=target_branch,
            title=title,
            body=body
        )

        with open(output_file, 'w') as stream:  # pylint: disable=open-builtin
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
        LOG.error("Unable to create pull request. Aborting")
        raise


if __name__ == "__main__":
    create_pull_request()  # pylint: disable=no-value-for-parameter
