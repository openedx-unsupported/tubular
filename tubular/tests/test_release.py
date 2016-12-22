"""
Tests for tubular.release.GitRelease
"""
from __future__ import unicode_literals

from datetime import datetime, timedelta
from unittest import TestCase

import ddt
from github import GithubException, Github
from github import UnknownObjectException
from github.Branch import Branch
from github.Commit import Commit
from github.CommitCombinedStatus import CommitCombinedStatus
from github.GitCommit import GitCommit
from github.GitRef import GitRef
from github.NamedUser import NamedUser
from github.Organization import Organization
from github.Repository import Repository
from mock import patch, Mock

from tubular import release
from tubular.release import NoValidCommitsError, GitRelease


@ddt.ddt
class GitHubApiTestCase(TestCase):
    """
    Tests the requests creation/response handling for the Github API
    All Network calls should be mocked out.
    """
    def setUp(self):
        with patch.object(Github, 'get_organization', return_value=Mock(spec=Organization)) as org_mock:
            with patch.object(Github, 'get_repo', return_value=Mock(spec=Repository)) as repo_mock:
                self.org_mock = org_mock.return_value = Mock(spec=Organization)
                self.repo_mock = repo_mock.return_value = Mock(spec=Repository)
                self.api = GitRelease('test-org', 'test-repo', token='abc123')
        super(GitHubApiTestCase, self).setUp()

    @patch('github.Github.get_user')
    def test_user(self, mock_user_method):
        # setup the mock
        mock_user_method.return_value = Mock(spec=NamedUser)

        self.assertIsInstance(self.api.user(), NamedUser)
        mock_user_method.assert_called()

    @ddt.data(
        ('abc', 'success'),
        ('123', 'failure'),
        (Mock(spec=GitCommit, **{'sha': '123'}), 'success'),
        (Mock(spec=GitCommit, **{'sha': '123'}), 'failure')
    )
    @ddt.unpack
    def test_commit_combined_statuses(self, sha, state):
        combined_status = Mock(spec=CommitCombinedStatus, state=state)
        attrs = {'get_combined_status.return_value': combined_status}
        commit_mock = Mock(spec=Commit, **attrs)
        self.repo_mock.get_commit = lambda sha: commit_mock

        status = self.api.commit_combined_statuses(sha)
        self.assertEqual(status.state, state)

    def test_commit_combined_statuses_passing_commit_obj(self):
        combined_status = Mock(spec=CommitCombinedStatus, **{'state': 'success'})
        attrs = {'get_combined_status.return_value': combined_status}
        commit_mock = Mock(spec=Commit, **attrs)
        self.repo_mock.get_commit = lambda sha: commit_mock

        status = self.api.commit_combined_statuses(commit_mock)
        self.assertEqual(status.state, 'success')

    def test_commit_combined_statuses_bad_object(self):
        self.assertRaises(UnknownObjectException, self.api.commit_combined_statuses, object())

    def test_get_commits_by_branch(self):
        self.repo_mock.get_branch.return_value = Mock(spec=Branch, **{'commit.sha': '123'})
        self.repo_mock.get_commits.return_value = [Mock(spec=Commit, sha=i) for i in range(10)]

        commits = self.api.get_commits_by_branch('test')

        self.repo_mock.get_branch.assert_called_with('test')
        self.repo_mock.get_commits.assert_called_with('123')
        self.assertEqual(len(commits), 10)

    def test_get_commits_by_branch_branch_not_found(self):
        self.repo_mock.get_branch.side_effect = GithubException(
            404,
            {
                'documentation_url': 'https://developer.github.com/v3/repos/#get-branch',
                'message': 'Branch not found'
            }
        )
        self.assertRaises(GithubException, self.api.get_commits_by_branch, 'blah')

    def test_delete_branch(self):
        ref_mock = Mock(spec=GitRef)
        get_git_ref_mock = Mock(return_value=ref_mock)
        self.repo_mock.get_git_ref = get_git_ref_mock
        self.api.delete_branch('blah')

        get_git_ref_mock.assert_called_with(ref='heads/blah')
        ref_mock.delete.assert_called()

    @ddt.data(
        ('blah-candidate', 'falafel'),
        ('meow', 'schwarma ')
    )
    @ddt.unpack
    def test_create_branch(self, branch_name, sha):
        create_git_ref_mock = Mock()
        self.repo_mock.create_git_ref = create_git_ref_mock

        self.api.create_branch(branch_name, sha)

        create_git_ref_mock.assert_called_with(ref='refs/heads/{}'.format(branch_name), sha=sha)

    @ddt.data(
        ('blah-candidate', 'release', 'test', 'test_pr'),
        ('catnip', 'release', 'My meowsome PR', 'this PR has lots of catnip inside, go crazy!'),
    )
    @ddt.unpack
    def test_create_pull_request(self, head, base, title, body):
        self.api.create_pull_request(
            head=head,
            base=base,
            title=title,
            body=body
        )
        self.repo_mock.create_pull.assert_called_with(
            head=head,
            base=base,
            title=title,
            body=body
        )

    @ddt.data(
        ('123', range(10), 'SuCcEsS', True),
        ('123', range(10), 'success', True),
        ('123', range(10), 'SUCCESS', True),
        ('123', range(10), 'pending', False),
        ('123', range(10), 'failure', False),
        ('123', range(10), None, False)
    )
    @ddt.unpack
    def test_is_commit_successful(self, sha, statuses, state, expected):
        mock_combined_status = Mock(spec=CommitCombinedStatus)
        mock_combined_status.statuses = statuses
        mock_combined_status.state = state

        commit_mock = Mock(spec=Commit)
        commit_mock.get_combined_status.return_value = mock_combined_status
        self.repo_mock.get_commit.return_value = commit_mock

        response = self.api.is_commit_successful(sha)

        self.assertEqual(response, expected)
        commit_mock.get_combined_status.assert_called()
        self.repo_mock.get_commit.assert_called_with(sha)

    @ddt.data(
        ('release-candidate', 4),
        ('meow-candidate', 6),
        ('should-have-gone-to-law-school', 1),
    )
    @ddt.unpack
    def test_most_recent_good_commit(self, branch, good_commit_id):
        commits = [Mock(spec=Commit, sha=i) for i in range(1, 10)]
        self.api.get_commits_by_branch = Mock(return_value=commits)

        def _side_effect(sha):
            """
            side effect returns True when the commit ID matches the current iteration
            """
            return sha == good_commit_id

        self.api.is_commit_successful = Mock(side_effect=_side_effect)

        self.api.most_recent_good_commit(branch)
        self.assertEqual(self.api.is_commit_successful.call_count, good_commit_id)

    def test_most_recent_good_commit_no_commit(self):
        commits = [Mock(spec=Commit, sha=i) for i in range(1, 10)]
        self.api.get_commits_by_branch = Mock(return_value=commits)

        self.api.is_commit_successful = Mock(return_value=False)
        self.assertRaises(NoValidCommitsError, self.api.most_recent_good_commit, 'release-candidate')


@ddt.ddt
class ReleaseUtilsTestCase(TestCase):
    """
    Test Cases for release utility functions
    """

    def test_rc_formatting(self):
        """
        Tests that rc branch names are properly formatted
        """
        date = datetime(year=1983, month=12, day=7, hour=6)
        name = GitRelease.rc_branch_name_for_date(date.date())
        self.assertEqual(name, 'rc/1983-12-07')

    @ddt.data(
        ('some title', 'some title'),
        (
            'some incredibly long title that will eventually be cut off',
            'some incredibly long title that will eventually be...'
        ),
        (
            'some title with\na new line in it',
            'some title with'
        ),
        (
            'some incredibly long title that will eventually be cut \noff',
            'some incredibly long title that will eventually be...'
        )
    )
    @ddt.unpack
    def test_extract_short(self, message, expected):
        """
        Tests that commit messages are properly summarized
        """
        summary = GitRelease.extract_message_summary(message)
        self.assertEqual(summary, expected)

    def mock_now(self, now=datetime(year=1983, month=12, day=7, hour=6)):
        """
        Patches datetime.now to provide the given date
        """
        # datetime.now can't be patched directly
        # so we have to go through this indirect route
        datetime_patcher = patch.object(
            release, 'datetime',
            Mock(wraps=datetime)
        )
        mocked_datetime = datetime_patcher.start()
        mocked_datetime.now.return_value = now  # pylint: disable=no-member
        self.addCleanup(datetime_patcher.stop)
        return now

    def test_start_after_current_day(self):
        """
        Tests that we don't start on the current day
        """
        now = self.mock_now()
        date = GitRelease.default_expected_release_date(now.weekday())
        self.assertEqual(date.weekday(), now.weekday())
        self.assertLess(now, date)

    def test_start_soon(self):
        """
        Tests that the next day is within the next week
        """
        now = self.mock_now()
        date = GitRelease.default_expected_release_date(now.weekday())
        self.assertEqual(date.weekday(), now.weekday())
        next_week = date + timedelta(weeks=1)
        self.assertLess(date, next_week)
