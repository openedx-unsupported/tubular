"""
Class containing utility methods for a GitHub release.
"""
from __future__ import unicode_literals

import string
from datetime import datetime, timedelta


class GitRelease(object):
    """
    Utility methods for a GitHub release.
    """
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
