"""
Tests for testeng-ci/release/utils
"""
from __future__ import unicode_literals

from datetime import datetime, timedelta
from unittest import TestCase

import ddt
import tubular.utils.release as utils
from tubular.github import GithubApi
from mock import patch, Mock


@ddt.ddt
class ReleaseUtilsTestCase(TestCase):
    """ Test Cases for release utility functions """

    def test_rc_formatting(self):
        """ Tests that rc branch names are properly formatted """
        date = datetime(year=1983, month=12, day=7, hour=6)
        name = utils.rc_branch_name_for_date(date.date())
        self.assertEqual(name, 'rc/1983-12-07')

    @ddt.data(
        ("some title", "some title"),
        (
            "some incredibly long title that will eventually be cut off",
            "some incredibly long title that will eventually be..."
        ),
        (
            "some title with\na new line in it",
            "some title with"
        ),
        (
            "some incredibly long title that will eventually be cut \noff",
            "some incredibly long title that will eventually be..."
        )
    )
    @ddt.unpack
    def test_extract_short(self, message, expected):
        """ Tests that commit messages are properly summarized """
        summary = utils.extract_message_summary(message)
        self.assertEqual(summary, expected)

    def mock_now(self, now=datetime(year=1983, month=12, day=7, hour=6)):
        """ Patches datetime.now to provide the given date """
        # datetime.now can't be patched directly
        # so we have to go through this indirect route
        datetime_patcher = patch.object(
            utils, 'datetime',
            Mock(wraps=datetime)
        )
        mocked_datetime = datetime_patcher.start()
        mocked_datetime.now.return_value = now  # pylint: disable=no-member
        self.addCleanup(datetime_patcher.stop)
        return now

    def test_start_after_current_day(self):
        """ Tests that we don't start on the current day """
        now = self.mock_now()
        date = utils.default_expected_release_date(now.weekday())
        self.assertEqual(date.weekday(), now.weekday())
        self.assertLess(now, date)

    def test_start_soon(self):
        """ Tests that the next day is within the next week """
        now = self.mock_now()
        date = utils.default_expected_release_date(now.weekday())
        self.assertEqual(date.weekday(), now.weekday())
        next_week = date + timedelta(weeks=1)
        self.assertLess(date, next_week)

    def test_no_parseable_commit_data(self):
        """
        Tests that if the JSON data we get back from Github is not parseable,
        then we abort
        """
        commits_mock = Mock()
        commits_mock.return_value = [{'sha': 'a'}, {'sha': 'b'}]

        commit_statuses_mock = Mock()
        commit_statuses_mock.side_effect = [
            {},
            {'foo': 'bar'},
        ]

        api = Mock(GithubApi)
        api.commits = commits_mock
        api.commit_statuses = commit_statuses_mock

        with self.assertRaises(utils.NoValidCommitsError):
            utils.most_recent_good_commit(api)

    def test_no_good_commits(self):
        """
        Tests that when there are no commits that passed checks, we abort
        """
        commits_mock = Mock()
        commits_mock.return_value = [{'sha': 'a'}, {'sha': 'b'}]

        commit_statuses_mock = Mock()
        commit_statuses_mock.side_effect = [
            {'state': 'failure'},
            {'state': 'pending'},
        ]

        api = Mock(GithubApi)
        api.commits = commits_mock
        api.commit_statuses = commit_statuses_mock

        with self.assertRaises(utils.NoValidCommitsError):
            utils.most_recent_good_commit(api)

    def test_good_commits(self):
        """
        Tests that we properly return the last valid commit
        """
        commits_mock = Mock()
        commits_mock.return_value = [{'sha': 'a'}, {'sha': 'b'}, {'sha': 'c'}]

        commit_statuses_mock = Mock()
        commit_statuses_mock.side_effect = [
            {'state': 'failure'},
            {},
            {'state': 'success'},
        ]

        api = Mock(GithubApi)
        api.commits = commits_mock
        api.commit_statuses = commit_statuses_mock

        commit = utils.most_recent_good_commit(api)
        self.assertEquals(commit['sha'], 'c')
