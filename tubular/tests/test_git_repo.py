"""
Tests for tubular.git_repo.GitRepo
"""
from __future__ import unicode_literals

import subprocess
from unittest import TestCase
import ddt
from mock import patch

from tubular.git_repo import GitRepo, merge_branch, InvalidGitRepoURL, GitMergeFailed


@ddt.ddt
class GitRepoTestCase(TestCase):
    """
    Tests the calls using the git CLI.
    All network calls are mocked out.
    """
    @patch('subprocess.check_call')
    @patch('subprocess.check_output')
    def test_merge_branch_success(self, mock_check_output, mock_check_call):
        """
        Tests merging a branch successfully.
        """
        merge_branch('git@github.com:edx/tubular.git', 'foo', 'bar')
        self.assertEqual(mock_check_call.call_count, 4)
        self.assertEqual(mock_check_output.call_count, 1)

    @patch('subprocess.check_call')
    @patch('subprocess.check_output')
    @ddt.data(
        (('git', 'clone'), 1),
        (('git', 'merge'), 2),
        (('git', 'push'), 3),
        (('git', 'rev-parse'), 4),
        (('rm', '-rf'), 5),
    )
    @ddt.unpack
    def test_merge_branch_failure(self, call_args, times_called, mock_check_output, mock_check_call):
        """
        Tests failing to merge a branch.
        """
        def side_effect(*args, **kwargs):  # pylint: disable=unused-argument
            """
            Trigger an exception for the right args.
            """
            if args[0][0:2] == list(call_args):
                raise subprocess.CalledProcessError([], 0)

        mock_check_call.side_effect = side_effect
        mock_check_output.side_effect = side_effect
        if call_args in (('git', 'clone'), ('rm', '-rf')):
            exception_to_expect = subprocess.CalledProcessError
        else:
            exception_to_expect = GitMergeFailed
        with self.assertRaises(exception_to_expect):
            merge_branch('git@github.com:edx/tubular.git', 'foo', 'bar')
            self.assertEqual(mock_check_call.call_count, times_called)

    @ddt.data(
        ('https://github.com/edx/edx-platform.git', True),
        ('https://github.com/edx-ops/secret_repo.git', False),
        ('git@github.com:edx/tubular.git', True),
        ('no_url_here', False),
    )
    @ddt.unpack
    def test_repo_url_parsing(self, repo_url, valid):
        """
        Tests the parsing of a repo URL passed into GitRepo.
        """
        if valid:
            GitRepo(repo_url)
        else:
            with self.assertRaises(InvalidGitRepoURL):
                GitRepo(repo_url)
