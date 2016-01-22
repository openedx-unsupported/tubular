"""
Utility functions using the GitHub API via the PyGithub module.
"""
import os
import github


# GitHub repo ID for edx-platform
# See: https://api.github.com/repos/edx/edx-platform
EDX_PLATFORM_REPO_ID = 10391073


class GitHubApiUtils(object):
    """
    Class to query/set GitHub info.
    """
    def __init__(self, repo_id):
        """
        Returns a GitHub object, possibly authed as a user.
        """
        token = os.environ.get('GITHUB_TOKEN', '')
        username = os.environ.get('GITHUB_USERNAME', '')
        password = os.environ.get('GITHUB_PASSWORD', '')
        if len(token):
            self.gh = github.Github(login_or_token=token)
        elif len(username) and len(password):
            self.gh = github.Github(login_or_token=username, password=password)
        else:
            # No auth available - use the API anonymously.
            self.gh = github.Github()
        self.repo = self.gh.get_repo(repo_id)

    def check_github_commit_test_status(self, commit_hash):
        """
        Given a commit hash (string), query the combined status of the commit's tests.
        """
        commit = self.repo.get_commit(commit_hash)
        pr_combined_status = commit.get_combined_status()
        if pr_combined_status.state == 'success':
            # All good!
            return True
        else:
            # All tests did not pass!
            return False

    def check_github_pr_test_status(self, pr_number):
        """
        Given a PR number (int), query the combined status of the PR's tests.
        """
        pull_request = self.repo.get_pull(pr_number)
        return self.check_github_commit_test_status(pull_request.head.sha)

    def is_branch_base_of_pr(self, pr_number, branch_name):
        """
        Check if the PR is against the specified branch,
        i.e. if the base of the PR is the specified branch.
        """
        pull_request = self.repo.get_pull(pr_number)
        repo_branch_name = 'edx:{}'.format(branch_name)
        return pull_request.base.label == repo_branch_name

    def get_head_commit_from_pr(self, pr_number):
        """
        Given a PR number, return the HEAD commit hash.
        """
        pull_request = self.repo.get_pull(pr_number)
        return pull_request.head.sha
