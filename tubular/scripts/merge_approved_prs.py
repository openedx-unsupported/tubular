#! /usr/bin/env python3

"""
Command-line script to trigger a jenkins job
"""
import click
import click_log

from tubular import github_api  # pylint: disable=wrong-import-position


def find_approved_prs(token, private_repo, public_repo, private_base_branch, public_base_branch):
    """
    Yield all PRs in ``private_repo`` which meet the following criteria:
        * have been approved
        * have not been closed
        * have a base branch of ``private_base_branch``
        * have not been merged to ``public_base_branch`` in ``public_repo``

    Arguments:
        token: A github access token
        private_repo (str, str): A tuple of org, repository
        public_repo (str, str): A tuple of org, repository
        private_base_branch (str): The name of the branch that PRs should be targetting
        public_base_branch (str): The name of a branch that PRs shouldn't have been merged to
    """
    private_github_repo = github_api.GitHubAPI(*private_repo, token=token)
    public_github_repo = github_api.GitHubAPI(*public_repo, token=token)

    candidate_prs = list(private_github_repo.find_approved_not_closed_prs(private_base_branch))

    for pull in candidate_prs:
        if not public_github_repo.has_been_merged(public_base_branch, pull.head.sha):
            yield pull


@click.command()
@click.option(
    '--token',
    help='The github access token, see https://help.github.com/articles/creating-an-access-token-for-command-line-use/',
    required=True,
)
@click.option(
    '--private-repo',
    help='The org, repo pair for the private repository.',
    nargs=2,
    required=True,
)
@click.option(
    '--private-base-branch',
    help='The branch in the private repository that PRs must target.',
    required=True,
)
@click.option(
    '--public-repo',
    help='The org of the public repository.',
    nargs=2,
    required=True,
)
@click.option(
    '--public-base-branch',
    help='The branch in the public repository that PRs must not be merged to.',
    required=True,
)
@click_log.simple_verbosity_option(default=u'INFO')
@click_log.init()
def octomerge(token, private_repo, public_repo, private_base_branch, public_base_branch):
    u"""
    Merge all approved security PRs into a release candidate.

    Any PR in ``privato-org/private-repo`` will be merged into ``private-branch``, as long
    as the PR meets the following conditions:

        * The PR has been approved (by at least one reviewer)
        * The PR has not been closed
        * The PR has not been merged to ``public-repo-path:public-base-branch``.
        * The PR is targeted at ``private-org/private-repo:private-base-branch``.
    """
    print("\n".join(pull.url for pull in find_approved_prs(
        token, private_repo, public_repo, private_base_branch, public_base_branch
    )))
