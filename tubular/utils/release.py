""" Assorted helpers for release tools """
from __future__ import print_function, unicode_literals
from datetime import datetime, timedelta
import string

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
    title = string.split(message, "\n")[0] or ''
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
    """ Returns the standard release candidate branch name """
    return "rc/{date}".format(date=date.isoformat())


def most_recent_good_commit(github_api):
    """
    Returns the most recent commit on master that has passed the tests
    """
    def _is_commit_successful(commit_sha):
        """
        Returns whether the passed commit has passed all its tests.
        Ensures there is at least one status update so that
        commits whose tests haven't started yet are not valid.
        """
        commit_status = github_api.commit_statuses(commit_sha)

        # Determine if the commit has passed all checks
        return commit_status.get('state') == 'success'

    commits = github_api.commits()

    result = None
    for commit in commits:
        if _is_commit_successful(commit['sha']):
            result = commit
            return result

    # no result
    raise NoValidCommitsError()
