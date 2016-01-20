import os
import sys
import click
from github_api_utils import GitHubApiUtils, EDX_PLATFORM_REPO_ID


@click.command()
@click.option('--repo_id', '-r',
              default=EDX_PLATFORM_REPO_ID,
              help="ID for the GitHub repository (defaults to edx-platform's ID).",
              required=False
              )
@click.option('--pr_number', '-p',
              default=None,
              help="Pull request number to check.",
              type=int,
              )
@click.option('--pr_env_var',
              help="Name of environment variable containing pull request number to check.",
              )
@click.option('--commit_hash', '-c',
              help="Commit hash to check.",
              )
@click.option('--commit_hash_env_var',
              help="Name of environment variable containing commit hash to check.",
              )
def cli(repo_id, pr_number, pr_env_var, commit_hash, commit_hash_env_var):
    """
    Check the combined status of a GitHub PR/commit in a repo.
    """
    # github.enable_console_debug_logging()
    gh = GitHubApiUtils(repo_id)

    if pr_number is None:
        if pr_env_var:
            pr_number = int(os.environ[pr_env_var])
    if commit_hash is None:
        if commit_hash_env_var:
            commit_hash = os.environ[commit_hash_env_var]

    status_success = False
    if pr_number:
        status_success = gh.check_github_pr_test_status(pr_number)
        print "{}: Combined status of PR #{} is {}.".format(
            sys.argv[0], pr_number, "success" if status_success else "failed"
        )
    elif commit_hash:
        status_success = gh.check_github_commit_test_status(commit_hash)
        print "{}: Combined status of commit hash {} is {}.".format(
            sys.argv[0], commit_hash, "success" if status_success else "failed"
        )

    # An exit code of 0 means success and non-zero means failure.
    sys.exit(not status_success)


if __name__ == '__main__':
    cli()
