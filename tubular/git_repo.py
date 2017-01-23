"""
Direct git commands on a GitHub repo.
"""
from __future__ import print_function, unicode_literals

from contextlib import contextmanager
import logging
import os
import re
import subprocess
from urlparse import urlparse

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class GitMergeFailed(Exception):
    """
    Raised when attempted git merge fails.
    """
    pass


class InvalidGitRepoURL(Exception):
    """
    Raised when repo URL can't be parsed.
    """
    pass


class GitRepo(object):
    """
    Performs direct git commands for a given GitHub repository.
    """
    def __init__(self, clone_url):
        # Verify and save the clone URL.
        parsed = urlparse(clone_url)
        self.clone_url = parsed.geturl()

        # Parse out the repository name.
        match = re.match(r'.*edx/(?P<name>.*).git', self.clone_url)
        if not match:
            raise InvalidGitRepoURL()
        self.name = match.group('name')

    def _exec_cmd(self, cmd_args):
        """
        Utility method for executing a command.
        Returns the exit code of the command.
        """
        LOGGER.info("Executing: {}".format(subprocess.list2cmdline(cmd_args)))
        return subprocess.check_call(cmd_args, stderr=subprocess.STDOUT)

    def _exec_cmd_output(self, cmd_args):
        """
        Utility method for executing a command.
        Returns the output of the command.
        """
        LOGGER.info("Executing: {}".format(subprocess.list2cmdline(cmd_args)))
        return subprocess.check_output(cmd_args, stderr=subprocess.STDOUT).strip()

    def clone(self, branch_name=None):
        """
        Clone the repo, optionally including only the history leading to the branch_name.

        Arguments:
            branch_name (str): Branch name to use in cloning history.

        Raises:
            subprocess.CalledProcessError: if the cmd fails
        """
        cmd_args = ['git', 'clone']
        if branch_name:
            cmd_args.extend(['--branch', branch_name])
        cmd_args.append(self.clone_url)
        self._exec_cmd(cmd_args)

    def new_branch(self, branch_name):
        """
        Create and check out a new branch.

        Arguments:
            branch_name (str): Branch name to create and checkout.

        Raises:
            subprocess.CalledProcessError: if the cmd fails
        """
        cmd_args = ['git', 'checkout', '-b', branch_name]
        self._exec_cmd(cmd_args)

    def track_branch(self, branch_name):
        """
        Track an existing branch.

        Arguments:
            branch_name (str): Branch name to track.

        Raises:
            subprocess.CalledProcessError: if the cmd fails
        """
        cmd_args = ['git', 'checkout', '-t', 'origin/{}'.format(branch_name)]
        self._exec_cmd(cmd_args)

    def merge(self,
              source_branch,
              ff_only):
        """
        Merge a source branch to the current branch, optionally forcing a fast-forward merge.

        Arguments:
            source_branch (str): Branch name containing commits to merge.
            ff_only(bool): If True, force a fast-forward merge.

        Raises:
            subprocess.CalledProcessError: if the cmd fails
        """
        cmd_args = ['git', 'merge']
        if ff_only:
            cmd_args.append('--ff-only')
        cmd_args.append(source_branch)
        self._exec_cmd(cmd_args)

    def push(self, branch_name):
        """
        Push branch to the remote.

        Arguments:
            branch_name (str): Branch name to push.

        Raises:
            subprocess.CalledProcessError: if the cmd fails
        """
        cmd_args = ['git', 'push', '-u', 'origin', branch_name]
        self._exec_cmd(cmd_args)

    def get_head_sha(self, branch_name):
        """
        Returns commit SHA of specified branch's HEAD.

        Arguments:
            branch_name (str): Branch name to use.

        Raises:
            subprocess.CalledProcessError: if the cmd fails
        """
        cmd_args = ['git', 'rev-parse', branch_name]
        return self._exec_cmd_output(cmd_args)

    def cleanup(self):
        """
        Delete the local clone of the repo.
        """
        cmd_args = ['rm', '-rf', self.name]
        self._exec_cmd(cmd_args)


@contextmanager
def _change_dir(repo):
    """
    Utility for changing into and out of a cloned GitRepo.
    """
    initial_directory = os.getcwd()
    os.chdir(repo.name)

    # Exception handler ensures that we always change back to the
    # initial directory, regardless of how control is returned
    # (e.g., an exception is raised while changed into the new directory).
    try:
        yield
    finally:
        os.chdir(initial_directory)


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
    repo = GitRepo(repo_url)
    repo.clone(source_branch)
    try:
        with _change_dir(repo):
            repo.track_branch(target_branch)
            repo.merge(source_branch, ff_only)
            repo.push(target_branch)
            merge_sha = repo.get_head_sha(target_branch)
    except subprocess.CalledProcessError as exc:
        raise GitMergeFailed(repr(exc.cmd))
    finally:
        repo.cleanup()
    return merge_sha
