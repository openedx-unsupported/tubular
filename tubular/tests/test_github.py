"""
Tests for tubular.github_api.GitHubAPI
"""
from __future__ import unicode_literals

from datetime import datetime, timedelta
from hashlib import sha1

from unittest import TestCase
import ddt
from mock import patch, Mock

from github import GithubException, Github
from github import UnknownObjectException
from github.Branch import Branch
from github.Commit import Commit
from github.Comparison import Comparison
from github.CommitCombinedStatus import CommitCombinedStatus
from github.GitCommit import GitCommit
from github.GitRef import GitRef
from github.Issue import Issue
from github.IssueComment import IssueComment
from github.NamedUser import NamedUser
from github.Organization import Organization
from github.PullRequest import PullRequest
from github.Repository import Repository

from tubular import github_api
from tubular.github_api import (
    GitHubAPI,
    NoValidCommitsError,
    InvalidPullRequestError,
    default_expected_release_date,
    extract_message_summary,
    rc_branch_name_for_date
)

# SHA1 is hash function designed to be difficult to reverse.
# This dictionary will help us map SHAs back to the hashed values.
SHA_MAP = {sha1(str(i)).hexdigest(): i for i in range(37)}
# These will be used as test data to feed test methods below which
# require SHAs.
SHAS = list(SHA_MAP.keys())
# This dictionary is used to convert trimmed SHAs back into the
# originally hashed values.
TRIMMED_SHA_MAP = {sha[:10]: i for sha, i in SHA_MAP.items()}


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
                self.api = GitHubAPI('test-org', 'test-repo', token='abc123')
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

    def test_create_tag(self):
        mock_user = Mock(spec=NamedUser)
        mock_user.email = 'testemail@edx.org'
        mock_user.name = 'test_name'
        with patch.object(Github, 'get_user', return_value=mock_user):
            create_tag_mock = Mock()
            create_ref_mock = Mock()
            self.repo_mock.create_git_tag = create_tag_mock
            self.repo_mock.create_git_ref = create_ref_mock

            test_tag = 'test_tag'
            test_sha = 'abc'
            self.api.create_tag(test_sha, test_tag)
            _, kwargs = create_tag_mock.call_args  # pylint: disable=unpacking-non-sequence
            self.assertEqual(kwargs['tag'], test_tag)
            self.assertEqual(kwargs['message'], '')
            self.assertEqual(kwargs['type'], 'commit')
            self.assertEqual(kwargs['object'], test_sha)
            create_ref_mock.assert_called_with(
                ref='refs/tags/{}'.format(test_tag),
                sha=test_sha
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

    @ddt.data(
        # 1 unique SHA should result in 1 search query and 1 PR.
        (SHAS[:1], 1, 1),
        # 18 unique SHAs should result in 1 search query and 18 PRs.
        (SHAS[:18], 1, 18),
        # 36 unique SHAs should result in 2 search queries and 36 PRs.
        (SHAS[:36], 2, 36),
        # 37 unique SHAs should result in 3 search queries and 37 PRs.
        (SHAS[:37], 3, 37),
        # 20 unique SHAs, each appearing twice, should result in 3 search queries and 20 PRs.
        (SHAS[:20] * 2, 3, 20),
    )
    @ddt.unpack
    @patch('github.Github.search_issues')
    def test_get_pr_range(self, shas, expected_search_count, expected_pull_count, mock_search_issues):
        commits = [Mock(spec=Commit, sha=sha) for sha in shas]
        self.repo_mock.compare.return_value = Mock(spec=Comparison, commits=commits)

        def search_issues_side_effect(shas, **kwargs):  # pylint: disable=unused-argument
            """
            Stub implementation of GitHub issue search.
            """
            return [Mock(spec=Issue, number=TRIMMED_SHA_MAP[sha]) for sha in shas.split()]

        mock_search_issues.side_effect = search_issues_side_effect

        self.repo_mock.get_pull = lambda number: Mock(spec=PullRequest, number=number)

        start_sha, end_sha = 'abc', '123'
        pulls = self.api.get_pr_range(start_sha, end_sha)

        self.repo_mock.compare.assert_called_with(start_sha, end_sha)

        self.assertEqual(mock_search_issues.call_count, expected_search_count)
        for call_args in mock_search_issues.call_args_list:
            # Verify that the batched SHAs have been trimmed.
            self.assertLess(len(call_args[0]), 200)

        self.assertEqual(len(pulls), expected_pull_count)
        for pull in pulls:
            self.assertIsInstance(pull, PullRequest)

    @ddt.data(
        ('macdiesel', 'Deployed to PROD', [':+1:', ':+1:', ':ship: :it:'], False, IssueComment),
        ('macdiesel', 'Deployed to stage', ['wahoo', 'want BLT', 'Deployed, to PROD, JK'], False, IssueComment),
        ('macdiesel', 'Deployed to PROD', [':+1:', 'law school man', '@macdiesel Deployed to PROD'], False, None),
        ('macdiesel', 'Deployed to stage', [':+1:', ':+1:', '@macdiesel dEpLoYeD tO stage'], False, None),
        ('macdiesel', 'Deployed to stage', ['@macdiesel dEpLoYeD tO stage', ':+1:', ':+1:'], False, None),
        ('macdiesel', 'Deployed to PROD', [':+1:', ':+1:', '@macdiesel Deployed to PROD'], True, IssueComment),
    )
    @ddt.unpack
    def test_message_pull_request(self, user, new_message, existing_messages, force_message, expected_result):
        comments = [Mock(spec=IssueComment, body=message) for message in existing_messages]
        self.repo_mock.get_pull.return_value = \
            Mock(spec=PullRequest,
                 get_issue_comments=Mock(return_value=comments),
                 create_issue_comment=lambda message: Mock(spec=IssueComment, body=message),
                 **{'user.login': user})

        result = self.api.message_pull_request(1, new_message, force_message)

        self.repo_mock.get_pull.assert_called()
        if expected_result:
            self.assertIsInstance(result, IssueComment)
            self.assertEqual(result.body, ''.join(['@', user, ' ', new_message]))
        else:
            self.assertEqual(result, expected_result)

    def test_message_pr_does_not_exist(self):
        with patch.object(self.repo_mock, 'get_pull', side_effect=UnknownObjectException(404, '')):
            self.assertRaises(InvalidPullRequestError, self.api.message_pull_request, 3, 'test')

    def test_message_pr_deployed_stage(self):
        with patch.object(self.api, 'message_pull_request') as mock:
            self.api.message_pr_deployed_stage(1, deploy_date=datetime(2017, 1, 10))
            mock.assert_called_with(1, github_api.PR_ON_STAGE_MESSAGE.format(date=datetime(2017, 1, 10)), False)

    @ddt.data(
        (datetime(2017, 1, 9), datetime(2017, 1, 10)),
        (datetime(2017, 1, 13), datetime(2017, 1, 16)),
    )
    @ddt.unpack
    def test_message_pr_deployed_stage_weekend(self, message_date, deploy_date):
        with patch.object(self.api, 'message_pull_request') as mock:
            with patch.object(github_api, 'datetime', Mock(wraps=datetime)) as mock_datetime:
                mock_datetime.now.return_value = message_date
                self.api.message_pr_deployed_stage(1)
                mock.assert_called_with(1, github_api.PR_ON_STAGE_MESSAGE.format(date=deploy_date), False)

    def test_message_pr_deployed_prod(self):
        with patch.object(self.api, 'message_pull_request') as mock:
            self.api.message_pr_deployed_prod(1)
            mock.assert_called_with(1, github_api.PR_ON_PROD_MESSAGE, False)

    def test_message_pr_release_canceled(self):
        with patch.object(self.api, 'message_pull_request') as mock:
            self.api.message_pr_release_canceled(1)
            mock.assert_called_with(1, github_api.PR_RELEASE_CANCELED_MESSAGE, False)


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
        name = rc_branch_name_for_date(date.date())
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
        summary = extract_message_summary(message)
        self.assertEqual(summary, expected)

    def mock_now(self, now=datetime(year=1983, month=12, day=7, hour=6)):
        """
        Patches datetime.now to provide the given date
        """
        # datetime.now can't be patched directly
        # so we have to go through this indirect route
        datetime_patcher = patch.object(
            github_api, 'datetime',
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
        date = default_expected_release_date([now.weekday()])
        self.assertEqual(date.weekday(), now.weekday())
        self.assertLess(now, date)

    def test_start_soon(self):
        """
        Tests that the next day is within the next week
        """
        now = self.mock_now()
        date = default_expected_release_date([now.weekday()])
        self.assertEqual(date.weekday(), now.weekday())
        next_week = date + timedelta(weeks=1)
        self.assertLess(date, next_week)
