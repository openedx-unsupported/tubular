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


class LocalGitAPI(object):
    """
    A set of helper functions for managing operations on local repos.
    """

    def __init__(self, repo):
        self.repo = repo

    @classmethod
    def clone(cls, repo_url, branch=None):
        """
        Initialize a LocalGitAPI by cloning a remote repo.

        Arguments:
            repo_url (str): The full url of the repo to clone. The last part of this
                url will be used as the repository directory name.
            branch (str): The branch to clone from
        """
        repo = Repo.clone_from(
            repo_url,
            to_path=extract_repo_name(repo_url),
            branch=branch
        )
        return cls(repo)

    def push_branch(self, branch):
        """
        Push a branch up to the remote server.
        """
        self.repo.git.push('origin', 'refs/heads/{}'.format(branch))

    def checkout_branch(self, branch):
        """
        Check out the specified branch.
        """
        self.repo.heads[branch].checkout()

    def merge_branch(self, source_branch, target_branch, ff_only=True):
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
        self.checkout_branch(target_branch)
        try:
            self.repo.git.merge(source_branch, ff_only=ff_only)
            merge_sha = self.repo.git.rev_parse('HEAD')
        finally:
            rmtree(self.repo.working_dir)
        return merge_sha

    def add_remote(self, remote_name, remote_url):
        """
        Add a remote named ``remote_name`` pointing to ``remote_url``
        to the repo at ``repo_path``.
        """
        self.repo.create_remote(remote_name, remote_url)

    def octopus_merge(self, base_branch, commitishes):
        """
        Merge all ``commitishes`` into ``base_branch``, inside ``repo_path``.
        """
        self.checkout_branch(base_branch)
        self.repo.git.merge(*commitishes)
