# pylint: disable=too-few-public-methods
""" Provides Access to the GitHub API """
from __future__ import print_function, unicode_literals

import logging
import string
from datetime import datetime, timedelta

from github import Github
from github.Commit import Commit
from github.GitCommit import GitCommit
from github.GithubException import UnknownObjectException

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class NoValidCommitsError(Exception):
    """
    Error indicating that there are no commits with valid statuses
    """
    pass


class GitRelease(object):
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

    # Day of week constant
    _TUESDAY = 1
    _NORMAL_RELEASE_WEEKDAY = _TUESDAY

    @staticmethod
    def extract_message_summary(message, max_length=50):
        """
        Take a commit message and return the first part of it.
        """
        title = string.split(message, '\n')[0] or ''
        if len(title) < max_length:
            return title
        else:
            return title[0:max_length] + '...'

    @staticmethod
    def default_expected_release_date(release_day=_NORMAL_RELEASE_WEEKDAY):
        """
        Returns the default expected release date given the current date.
        Currently the nearest Tuesday in the future (can't be today)
        """
        proposal = datetime.now() + timedelta(days=1)
        while proposal.weekday() is not release_day:
            proposal = proposal + timedelta(days=1)
        return proposal

    @staticmethod
    def rc_branch_name_for_date(date):
        """
        Returns the standard release candidate branch name
        """
        return 'rc/{date}'.format(date=date.isoformat())
