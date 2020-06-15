"""
Direct git commands on a GitHub repo.
"""

import logging
import re
from contextlib import contextmanager

from git import Repo
from git.exc import GitCommandError
from git.util import rmtree
from six.moves import urllib

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)


class InvalidGitRepoURL(Exception):
    """
    Raised when repo URL can't be parsed.
    """


class FastForwardMergeImpossible(Exception):
    """
    Raised when attempting a fast-forward-only merge that can't be done.
    """


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


class LocalGitAPI:
    """
    A set of helper functions for managing operations on local repos.
    """

    def __init__(self, repo):
        self.repo = repo

    @classmethod
    def clone(cls, repo_url, branch=None, reference_repo=None):
        """
        Initialize a LocalGitAPI by cloning a remote repo.

        Arguments:
            repo_url (str): The full url of the repo to clone. The last part of this
                url will be used as the repository directory name.
            branch (str): The branch to clone from
            reference_repo (str): A path to a reference repo (to speed up clones)
        """
        kwargs = {}

        if reference_repo:
            kwargs['reference'] = reference_repo

        repo = Repo.clone_from(
            repo_url,
            to_path=extract_repo_name(repo_url),
            branch=branch,
            **kwargs
        )
        return cls(repo)

    def push_branch(self, branch, remote='origin', remote_branch=None, force=False):
        """
        Push a branch up to the remote server, optionally with a different name.
        """
        if remote_branch:
            push_ref = 'refs/heads/{}:refs/heads/{}'.format(branch, remote_branch)
        else:
            push_ref = 'refs/heads/{}'.format(branch)
        self.repo.remotes[remote].push(push_ref, force=force)

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
        except GitCommandError as exc:
            if '--ff-only' in exc.command and exc.status == 128:
                raise FastForwardMergeImpossible(' '.join(exc.command))
            raise
        merge_sha = self.repo.git.rev_parse('HEAD')
        return merge_sha

    def add_remote(self, remote_name, remote_url):
        """
        Add a remote named ``remote_name`` pointing to ``remote_url``
        to this repo.
        """
        remote = self.repo.create_remote(remote_name, remote_url)
        remote.fetch()

    def get_head_sha(self, branch=None):
        """
        Gets the HEAD commit sha for the repo.
        """
        if branch:
            return self.repo.heads[branch].commit.hexsha
        else:
            return self.repo.head.commit.hexsha

    def create_branch(self, branch_name, commit='HEAD'):
        """
        Creates a branch with a specified name in the local repo.
        """
        self.repo.create_head(branch_name, commit)

    def track_remote_branch(self, remote_name, remote_branch):
        """
        Create a local branch which tracks a remote branch.
        """
        branch_ref = self.repo.remote(remote_name).refs[remote_branch]
        self.create_branch(remote_branch, branch_ref)
        self.repo.heads[remote_branch].set_tracking_branch(branch_ref)
        self.checkout_branch(remote_branch)

    def octopus_merge(self, base_branch, commitishes):
        """
        Merge all ``commitishes`` into ``base_branch`` in this repo.
        """
        self.checkout_branch(base_branch)
        if commitishes:
            self.repo.git.merge(*commitishes)
        return self.get_head_sha()

    def push_tags(self, remote='origin', force=False):
        """
        Push all local tags up to the remote repo.
        """
        push_ref = 'refs/tags/*'
        self.repo.remotes[remote].push(push_ref, force=force)

    def force_branch_to(self, branch, commitish, remote=None):
        """
        Reset branch to commitish.

        Arguments:
            branch: the branch to reset
            commitish: The commit to reset the branch to.
            remote: The remote containing ``commitish``.
        """
        if remote:
            commitish = self.repo.remotes[remote].refs[commitish]

        if self.repo.active_branch == self.repo.heads[branch]:
            self.repo.head.reset(commitish, index=True, working_tree=True)
        else:
            self.repo.heads[branch].reset(commitish, index=True)

    @contextmanager
    def cleanup(self):
        """
        Delete the repo working directory when this contextmanager is finished.
        """
        try:
            yield self
        finally:
            rmtree(self.repo.working_dir)
