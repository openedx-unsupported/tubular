"""
Tests for tubular.git_repo.GitRepo
"""

from unittest import TestCase

import ddt
from git import GitCommandError, Repo
from mock import patch, MagicMock

from tubular.git_repo import LocalGitAPI, InvalidGitRepoURL, extract_repo_name


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
        with LocalGitAPI.clone('git@github.com:edx/tubular.git', 'bar').cleanup() as repo:
            merge_sha = repo.merge_branch('foo', 'bar')

        mock_repo.clone_from.assert_called_once_with(
            'git@github.com:edx/tubular.git', to_path='tubular', branch='bar',
        )
        git_wrapper = mock_repo.clone_from.return_value.git
        git_wrapper.merge.assert_called_once_with('foo', ff_only=True)
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
            LocalGitAPI.clone('git@github.com:edx/tubular.git', 'bar')
        self.assertEqual(mock_rmtree.call_count, 0)

    @patch('tubular.git_repo.rmtree', autospec=True)
    @patch('tubular.git_repo.Repo')
    @ddt.data(
        'clone_from.return_value.git.merge',
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
            LocalGitAPI.clone('git@github.com:edx/tubular.git', 'bar').merge_branch('foo', 'bar')
            mock_rmtree.assert_called_once_with('tubular')

    def test_octopus_merge(self):
        mock_repo = MagicMock(spec=Repo)
        api = LocalGitAPI(mock_repo)
        sha = api.octopus_merge('public/release-candidate', ['12345abcdef', 'deadbeef'])

        mock_repo.git.merge.assert_called_once_with('12345abcdef', 'deadbeef')
        self.assertEqual(sha, mock_repo.head.commit.hexsha)

    def test_empty_octopus_merge(self):
        mock_repo = MagicMock(spec=Repo)
        api = LocalGitAPI(mock_repo)
        sha = api.octopus_merge('public/release-candidate', [])

        mock_repo.git.merge.assert_not_called()
        self.assertEqual(sha, mock_repo.head.commit.hexsha)

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
