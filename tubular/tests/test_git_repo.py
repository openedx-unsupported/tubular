"""
Tests for tubular.git_repo.GitRepo
"""
from __future__ import absolute_import
from __future__ import unicode_literals

from unittest import TestCase
import ddt
from git import GitCommandError
from mock import patch

from tubular.git_repo import merge_branch, InvalidGitRepoURL, extract_repo_name


@ddt.ddt
class GitRepoTestCase(TestCase):
    """
    Tests the calls using the git CLI.
    All network calls are mocked out.
    """
    @patch('tubular.git_repo.rmtree', autospec=True)
    @patch('tubular.git_repo.Repo', autospec=True)
    def test_merge_branch_success(self, mock_repo, mock_rmtree):
        """
        Tests merging a branch successfully.
        """
        merge_sha = merge_branch('git@github.com:edx/tubular.git', 'foo', 'bar')

        mock_repo.clone_from.assert_called_once_with(
            'git@github.com:edx/tubular.git', to_path='tubular', branch='bar'
        )
        git_wrapper = mock_repo.clone_from.return_value.git
        git_wrapper.merge.assert_called_once_with('foo', ff_only=True)
        git_wrapper.push.assert_called_once_with('origin', 'refs/heads/bar')
        git_wrapper.rev_parse.assert_called_once_with('HEAD')
        self.assertEqual(git_wrapper.rev_parse.return_value, merge_sha)
        mock_rmtree.assert_called_once_with(mock_repo.clone_from.return_value.working_dir)

    @patch('tubular.git_repo.rmtree', autospec=True)
    @patch('tubular.git_repo.Repo', autospec=True)
    def test_clone_failure(self, mock_repo, mock_rmtree):
        """
        Tests failing to merge a branch.
        """
        mock_repo.clone_from.side_effect = GitCommandError('cmd', 1)

        with self.assertRaises(GitCommandError):
            merge_branch('git@github.com:edx/tubular.git', 'foo', 'bar')
        self.assertEqual(mock_rmtree.call_count, 0)

    @patch('tubular.git_repo.rmtree', autospec=True)
    @patch('tubular.git_repo.Repo')
    @ddt.data(
        'clone_from.return_value.git.merge',
        'clone_from.return_value.git.push',
        'clone_from.return_value.git.rev_parse',
    )
    def test_cleanup(self, failing_mock, mock_repo, mock_rmtree):
        """
        Tests failing to merge a branch.
        """
        mock_repo.configure_mock(
            autospec=True,
            **{'{}.side_effect'.format(failing_mock): GitCommandError('cmd', 1)}
        )

        with self.assertRaises(GitCommandError):
            merge_branch('git@github.com:edx/tubular.git', 'foo', 'bar')
            mock_rmtree.assert_called_once_with('tubular')

    @ddt.data(
        ('https://github.com/edx/edx-platform.git', 'edx-platform'),
        ('https://github.com/edx-ops/secret_repo.git', 'secret_repo'),
        ('git@github.com:edx/tubular.git', 'tubular'),
        ('no_url_here', None),
    )
    @ddt.unpack
    def test_repo_url_parsing(self, repo_url, result):
        """
        Tests the parsing of a repo URL passed into GitRepo.
        """
        if result:
            self.assertEqual(extract_repo_name(repo_url), result)
        else:
            with self.assertRaises(InvalidGitRepoURL):
                extract_repo_name(repo_url)
