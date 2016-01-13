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
              required=True
              )
@click.option('--branch_name', '-b',
              default=None,
              help="Branch to check if the base of the PR.",
              type=str,
              required=True
              )
def cli(repo_id, pr_number, branch_name):
    """
    Check if the PR is against the specified branch,
    i.e. if the base of the PR is the specified branch.
    """
    # github.enable_console_debug_logging()
    gh = GitHubApiUtils(repo_id)
    return gh.is_branch_base_of_pr(pr_number, branch_name)


if __name__ == '__main__':
    cli()
