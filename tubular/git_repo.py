"""
Direct git commands on a GitHub repo.
"""
from __future__ import absolute_import
from __future__ import print_function, unicode_literals

import logging
import re

from six.moves import urllib
from git import Repo
from git.util import rmtree


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class InvalidGitRepoURL(Exception):
    """
    Raised when repo URL can't be parsed.
    """
    pass


def extract_repo_name(repo_url):
    """
    Extract the name of a git repository from its clone url.
    """
    parsed = urllib.parse.urlparse(repo_url)
    clone_url = parsed.geturl()

    # Parse out the repository name.
    match = re.match(r'.*/(?P<name>[^/]*).git', clone_url)
    if not match:
        raise InvalidGitRepoURL()
    return match.group('name')


def merge_branch(repo_url,
                 source_branch,
                 target_branch,
                 ff_only=True):
    """
    Merge a source branch into a target branch, optionally forcing a fast-forward merge.

    Arguments:
        repo_url (str): URL of GitHub repository.
        source_branch (str): Branch name containing commits to merge.
        target_branch (str): Branch name into which the source branch will be merged.
        ff_only(bool): If True, force a fast-forward merge.

    Returns:
        Commit SHA of the merge commit where the branch was merged.
    """
    repo = Repo.clone_from(repo_url, to_path=extract_repo_name(repo_url), branch=target_branch)
    try:
        repo.git.merge(source_branch, ff_only=ff_only)
        repo.git.push('origin', 'refs/heads/{}'.format(target_branch))
        merge_sha = repo.git.rev_parse('HEAD')
    finally:
        rmtree(repo.working_dir)
    return merge_sha


def add_remote(repo_path, remote_name, remote_url):
    """
    Add a remote named ``remote_name`` pointing to ``remote_url``
    to the repo at ``repo_path``.
    """
    repo = Repo(repo_path)
    repo.create_remote(remote_name, remote_url)
