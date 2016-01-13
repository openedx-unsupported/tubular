import click
from github_utils import GitHubApiUtils, EDX_PLATFORM_REPO_ID


@click.command()
@click.option('--repo_id', '-r',
              default=EDX_PLATFORM_REPO_ID,
              help="ID for the GitHub repository (defaults to edx-platform's ID).",
              type=int,
              required=False
              )
@click.option('--pr_number', '-p',
              default=None,
              help="Pull request number to check.",
              type=int,
              required=False
              )
@click.option('--commit_hash', '-c',
              default=None,
              help="Commit hash to check.",
              type=str,
              required=False
              )
def cli(repo_id, pr_number, commit_hash):
    """
    Check the combined status of a GitHub PR/commit in a repo.
    """
    # github.enable_console_debug_logging()
    gh = GitHubApiUtils(repo_id)
    if pr_number:
        return gh.check_github_pr_test_status(pr_number)
    elif commit_hash:
        return gh.check_github_commit_test_status(commit_hash)
    else:
        return False


if __name__ == '__main__':
    cli()
