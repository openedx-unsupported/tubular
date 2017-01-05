"""
Tests for tubular.release.GitRelease
"""
from __future__ import unicode_literals

from datetime import datetime, timedelta
from unittest import TestCase

import ddt
from mock import patch, Mock

from tubular import release
from tubular.release import GitRelease


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
