""" Provides Access to the GitHub API """
from __future__ import print_function, unicode_literals

from datetime import datetime, timedelta
import logging
import os
import string

from github import Github
from github.Commit import Commit
from github.GitCommit import GitCommit
from github.GithubException import UnknownObjectException

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


# Day of week constant
_TUESDAY = 1
_NORMAL_RELEASE_WEEKDAY = _TUESDAY


class NoValidCommitsError(Exception):
    """
    Error indicating that there are no commits with valid statuses
    """
    pass


def extract_message_summary(message, max_length=50):
    """
    Take a commit message and return the first part of it.
    """
    title = string.split(message, '\n')[0] or ''
    if len(title) < max_length:
        return title
    else:
        return title[0:max_length] + '...'


def default_expected_release_date(release_day=_NORMAL_RELEASE_WEEKDAY):
    """
    Returns the default expected release date given the current date.
    Currently the nearest Tuesday in the future (can't be today)
    """
    proposal = datetime.now() + timedelta(days=1)
    while proposal.weekday() is not release_day:
        proposal = proposal + timedelta(days=1)
    return proposal


def rc_branch_name_for_date(date):
    """
    Returns the standard release candidate branch name
    """
    return 'rc/{date}'.format(date=date.isoformat())


class GitHubAPI(object):
    """
    Manages requests to the GitHub api for a given org/repo
    """

    def __init__(self, org, repo, token):
        """
        Creates a new API access object.

        Arguments:
            org (string): Github org to access
            repo (string): Github repo to access
            token (string): Github API access token

        """
        self.github_connection = Github(token)
        self.github_repo = self.github_connection.get_repo('{org}/{repo}'.format(org=org, repo=repo))
        self.github_org = self.github_connection.get_organization(org)
        self.org = org
        self.repo = repo

    def user(self):
        """
        Calls GitHub's '/user' endpoint.
            See
            https://developer.github.com/v3/users/#get-the-authenticated-user

        Returns:
            github.NamedUser.NamedUser: Information about the current user.

        Raises:
            RequestFailed: If the response fails validation.
        """
        return self.github_connection.get_user()

    def get_head_commit_from_pull_request(self, pr_number):
        """
        Given a PR number, return the HEAD commit hash.

        Arguments:
            pr_number (int): Number of PR to check.

        Returns:
            Commit SHA of the PR HEAD.

        Raises:
            github.GithubException.GithubException: If the response fails.
            github.GithubException.UnknownObjectException: If the branch does not exist
        """
        return self.get_pull_request(pr_number).head.sha

    def check_pull_request_test_status(self, pr_number):
        """
        Given a PR number, query the combined status of the PR's tests.

        Arguments:
            pr_number (int): Number of PR to check.

        Returns:
            True if all tests have passed successfully, else False.

        Raises:
            github.GithubException.GithubException: If the response fails.
            github.GithubException.UnknownObjectException: If the branch does not exist
        """
        return self.commit_combined_statuses(self.get_head_commit_from_pull_request(pr_number)).state == 'success'

    def is_branch_base_of_pull_request(self, pr_number, branch_name):
        """
        Check if the PR is against the specified branch,
        i.e. if the base of the PR is the specified branch.

        Arguments:
            pr_number (int): Number of PR to check.
            branch_name (str): Name of branch to check.

        Returns:
            True if PR is opened against the branch, else False.

        Raises:
            github.GithubException.GithubException: If the response fails.
            github.GithubException.UnknownObjectException: If the branch does not exist
        """
        pull_request = self.get_pull_request(pr_number)
        repo_branch_name = '{}:{}'.format(self.org, branch_name)
        return pull_request.base.label == repo_branch_name

    def commit_combined_statuses(self, commit):
        """
        Calls GitHub's '<commit>/statuses' endpoint for a given commit. See
        https://developer.github.com/v3/repos/statuses/#get-the-combined-status-for-a-specific-ref

        Returns:
            github.CommitCombinedStatus.CommitCombinedStatus

        Raises:
            RequestFailed: If the response fails validation.
        """
        if isinstance(commit, (str, unicode)):
            commit = self.github_repo.get_commit(commit)
        elif isinstance(commit, GitCommit):
            commit = self.github_repo.get_commit(commit.sha)
        elif not isinstance(commit, Commit):
            raise UnknownObjectException(500, 'commit is neither a valid sha nor github.Commit.Commit object.')

        return commit.get_combined_status()

    def get_commits_by_branch(self, branch):
        """
        Calls GitHub's 'commits' endpoint for master.
        See
        https://developer.github.com/v3/repos/commits/#list-commits-on-a-repository

        Arguments:
            branch (str): branch to search for commits.

        Returns:
            github.PaginatedList.PaginatedList: of github.GitCommit.GitCommit

        Raises:
            github.GithubException: If the response fails validation.
        """
        branch = self.github_repo.get_branch(branch)
        return self.github_repo.get_commits(branch.commit.sha)

    def delete_branch(self, branch_name):
        """
        Call GitHub's delete ref (branch) API

        Args:
            branch_name (str): The name of the branch to delete

        Raises:
            github.GithubException.GithubException: If the response fails.
            github.GithubException.UnknownObjectException: If the branch does not exist
        """
        ref = self.github_repo.get_git_ref(
            ref='heads/{ref}'.format(ref=branch_name)
        )
        ref.delete()

    def create_branch(self, branch_name, sha):
        """
        Calls GitHub's create ref (branch) API

        Arguments:
            branch_name (str): The name of the branch to create
            sha (str): The commit to base the branch off of

        Returns:
            github.GitRef.GitRef

        Raises:
            github.GithubException.GithubException: If the branch isn't created/already exists.
            github.GithubException.UnknownObjectException: if the branch can not be fetched after creation
        """
        return self.github_repo.create_git_ref(
            ref='refs/heads/{}'.format(branch_name),
            sha=sha
        )

    def create_pull_request(
            self,
            head,
            base='release',
            title='',
            body=''):
        """
        Creates a new pull request from a branch

        Arguments:
            head (str): The name of the branch to create the PR from
            base (str): The Branch the PR will be merged in to
            title (str): Title of the pull request
            body (str): Text body of the pull request

        Returns:
            github.PullRequest.PullRequest

        Raises:
            github.GithubException.GithubException:

        """
        return self.github_repo.create_pull(
            title=title,
            body=body,
            head=head,
            base=base
        )

    def get_pull_request(self, pr_number):
        """
        Given a PR number, return the PR object.

        Arguments:
            pr_number (int): Number of PR to get.

        Returns:
            github.PullRequest.PullRequest

        Raises:
            github.GithubException.GithubException: If the response fails.
            github.GithubException.UnknownObjectException: If the PR ID does not exist
        """
        return self.github_repo.get_pull(pr_number)

    def merge_pull_request(self, pr_number):
        """
        Given a PR number, merge the pull request (if possible).

        Arguments:
            pr_number (int): Number of PR to merge.

        Raises:
            github.GithubException.GithubException: If the PR merge fails.
            github.GithubException.UnknownObjectException: If the PR ID does not exist.
        """
        pull_request = self.get_pull_request(pr_number)
        pull_request.merge()

    def is_commit_successful(self, sha):
        """
        Returns whether the passed commit has passed all its tests.
        Ensures there is at least one status update so that
        commits whose tests haven't started yet are not valid.

        Arguments:
            sha (str): The SHA of which to get the status.

        Returns:
            bool: true when the combined state equals 'success'
        """
        commit_status = self.commit_combined_statuses(sha)

        # Determine if the commit has passed all checks
        if len(commit_status.statuses) < 1 or commit_status.state is None:
            return False

        return commit_status.state.lower() == 'success'

    def most_recent_good_commit(self, branch):
        """
        Returns the most recent commit on master that has passed the tests

        Arguments:
            branch (str): branch name to check for valid commits

        Returns:
            github.GitCommit.GitCommit

        Raises:
            NoValidCommitsError: When no commit is found

        """
        commits = self.get_commits_by_branch(branch)

        result = None
        for commit in commits:
            if self.is_commit_successful(commit.sha):
                result = commit
                return result

        # no result
        raise NoValidCommitsError()

    def get_pr_range(self, start_sha, end_sha):
        """
        Given a start SHA and an end SHA, returns a list of PRs between the two,
        excluding the start SHA and including the end SHA.

        This has been done in the past by parsing PR numbers out of merge commit
        messages. However, merge commits are becoming less common on GitHub with
        the advent of new PR merge strategies (i.e., squash merge, rebase merge).
        If you merge a PR using either squash or rebase merging, there will be no
        merge commit corresponding to your PR on master. The merge commit message
        parsing approach will subsequently fail to locate your PR.

        The GitHub Search API helps us address this by allowing us to search issues
        by SHA. Note that the GitHub Search API has custom rate limit rules (30 RPM).
        For more, see https://developer.github.com/v3/search.

        Arguments:
            start_sha (str): SHA from which to begin the PR search, exclusive.
            end_sha (str): SHA at which to conclude the PR search, inclusive.

        Returns:
            list: of github.PullRequest.PullRequest
        """
        # The Search API limits search queries to 256 characters. Untrimmed SHA1s
        # are 40 characters long. To avoid exceeding the rate and search query size
        # limits, we can batch SHAs in our searches. Reserving 56 characters for
        # qualifiers (i.e., type, base, user, repo) leaves us with 200 characters.
        # As with all other terms in the query, the batched SHAs need to be separated
        # by a character of whitespace. A batch size of 18 10-character SHAs requires
        # 17 characters of whitespace, for a total of 18*10 + 17 = 197 characters.
        # We'd need to search for >540 commits in a minute to exceed the rate limit.
        sha_length = int(os.environ.get('SHA_LENGTH', 10))
        batch_size = int(os.environ.get('BATCH_SIZE', 18))

        def batch(batchable):
            """
            Utility to facilitate batched iteration over a list.

            Arguments:
                batchable (list): The list to break into batches.

            Yields:
                list
            """
            length = len(batchable)
            for index in range(0, length, batch_size):
                yield batchable[index:index + batch_size]

        comparison = self.github_repo.compare(start_sha, end_sha)
        shas = [commit.sha[:sha_length] for commit in comparison.commits]

        issues = []
        for sha_batch in batch(shas):
            # For more about searching issues,
            # see https://help.github.com/articles/searching-issues.
            issues += self.github_connection.search_issues(
                ' '.join(sha_batch),
                type='pr',
                base='master',
                user=self.org,
                repo=self.repo,
            )

        pulls = {}
        for issue in issues:
            # Merge commits link back to the same PR as the actual commits merged
            # by that PR. We want to avoid listing the PR twice in this situation,
            # and also when a PR includes more than one commit.
            if not pulls.get(issue.number):
                pulls[issue.number] = self.github_repo.get_pull(issue.number)

        return list(pulls.values())
