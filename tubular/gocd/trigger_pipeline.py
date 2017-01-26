"""
Trigger a GoCD pipeline for a particular GitHub repo/PR.
"""
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import sys
import click
from .gocd_api_utils import GoCDApiUtils


@click.command()
@click.option(
    '--pipeline_name',
    help="Name of pipeline to trigger.",
    required=True,
)
@click.option(
    '--org',
    help='Org from the GitHub repository URL of https://github.com/<org>/<repo>',
    default='edx'
)
@click.option(
    '--repo',
    help='Repo name from the GitHub repository URL of https://github.com/<org>/<repo>',
    required=True
)
@click.option(
    '--token',
    envvar='GIT_TOKEN',
    help='The github access token, see https://help.github.com/articles/creating-an-access-token-for-command-line-use/'
)
@click.option(
    '--pr_id',
    default=None,
    help="ID of GitHub pull request containing code to merge.",
    type=int,
    required=True,
)
def cli(pipeline_name, org, repo, token, pr_id):
    """
    Trigger a GoCD pipeline using the specified GitHub repo/PR/branch.
    """
    success = GoCDApiUtils().trigger_pipeline(pipeline_name, org, repo, token, pr_id)
    if success:
        print("Schedule of pipeline {} for repo {} and PR {}: success.".format(pipeline_name, repo, pr_id))
    # An exit code of 0 means success and non-zero means failure.
    sys.exit(not success)


if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter
