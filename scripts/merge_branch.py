"""
Command-line script to merge a branch.
"""
from os import path
import sys
import logging
import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.git_repo import merge_branch as merge_repo_branch  # pylint: disable=wrong-import-position

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
def merge_branch(org,
                 repo,
                 source_branch,
                 target_branch,
                 fast_forward_only):
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
    github_url = u'https://github.com/{}/{}.git'.format(org, repo)
    merge_repo_branch(github_url, source_branch, target_branch, fast_forward_only)

if __name__ == u"__main__":
    merge_branch()  # pylint: disable=no-value-for-parameter
