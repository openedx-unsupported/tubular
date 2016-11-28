# pylint: disable=too-few-public-methods
""" Provides Access to the GitHub API """
from __future__ import unicode_literals

import requests
from requests.auth import AuthBase


GITHUB_API_VERSION = "application/vnd.github.v3+json"


class RequestFailed(Exception):
    """
    Exception indicating a network request failed.
    """
    def __init__(self, response):
        payload = {
            "url": response.url,
            "code": response.status_code,
            "response": response.content
        }
        super(RequestFailed, self).__init__(payload)
        self.response = response


class TokenAuth(AuthBase):
    """
    Authorization method for requests library supporting github OAuth tokens.
    """
    def __init__(self, token):
        self.token = token

    def __call__(self, request):
        request.headers["Authorization"] = "token %s" % self.token
        return request


class GithubApi(object):
    """
    Manages requests to the GitHub api for a given org/repo
    """

    def __init__(self, org, repo, token):
        """
        Creates a new API access object.

        Arguments:
            org (string): Github org to access
            repo (string): Github repo to access

        """
        self.token = token
        self.org = org
        self.repo = repo

    def _request(self, path, method, success_code=200, **kwargs):
        """
        Performs a network request, validating its success.

        Arguments:
            path (string): An api path. Does not need to include the the url
                domain.
            method (string): An HTTP method like `'GET'` or `'POST'`.
            success_code (int): The expected response code. Will raise
                `RequestFailed` if the response doesn't match this code.
                Defaults to 200.
            kwargs (dict): Additional arguments are forwarded on to the request
                constructor

        Returns:
            json: The output of the endpoint as a json object.

        Raises:
            RequestFailed: If the response fails validation.
        """
        url = ("https://api.github.com/%s" % path).format(
            repo=self.repo, org=self.org
        )
        auth = TokenAuth(self.token)
        headers = {"Accept": GITHUB_API_VERSION}
        response = requests.request(
            method, url, auth=auth, headers=headers, **kwargs
        )
        if response.status_code != success_code:
            raise RequestFailed(response)
        # some response codes are not expected to have any content
        if response.text:
            return response.json()
        else:
            return

    def _get(self, path):
        """
        Performs a network `GET` request, validating its success.

        Arguments:
            path (string): An api path. Does not need to include the the url
                domain.

        Returns:
            json: The output of the endpoint as a json object.

        Raises:
            RequestFailed: If the response fails validation.
        """
        return self._request(path, 'GET')

    def _post(self, path, args):
        """
        Performs a network `POST` request, validating its success.

        Arguments:
            path (string): An api path. Does not need to include the the url
                domain.
            args (json): Arguments to the endpoint

        Returns:
            json: The output of the endpoint as a json object.

        Raises:
            RequestFailed: If the response fails validation.
        """
        return self._request(path, 'POST', success_code=201, json=args)

    def _delete(self, path):
        """
        Performs a network `DELETE` request, validating its success.

        Arguments:
            path (string): An api path. Does not need to include the the url
                domain.

        Returns:
            json: The output of the endpoint as a json object.

        Raises:
            RequestFailed: If the response fails validation.
        """
        return self._request(path, 'DELETE', success_code=204)

    def user(self):
        """
        Calls GitHub's '/user' endpoint.
            See
            https://developer.github.com/v3/users/#get-the-authenticated-user

        Returns:
            dict: Information about the current user.

        Raises:
            RequestFailed: If the response fails validation.
        """
        return self._get("user")

    def commit_statuses(self, commit_sha):
        """
        Calls GitHub's '<commit>/statuses' endpoint for a given commit. See
        https://developer.github.com/v3/repos/statuses/#get-the-combined-status-for-a-specific-ref

        Returns:
            list: A list of commit statuses

        Raises:
            RequestFailed: If the response fails validation.
        """
        path = "repos/{org}/{repo}/commits/%s/status" % commit_sha
        return self._get(path)

    def commits(self):
        """
        Calls GitHub's 'commits' endpoint for master.
        See
        https://developer.github.com/v3/repos/commits/#list-commits-on-a-repository

        Returns:
            A list of the most recent commits for the master branch.

        Raises:
            RequestFailed: If the response fails validation.
        """
        path = "repos/{org}/{repo}/commits"
        return self._get(path)

    def delete_branch(self, branch_name):
        """
        Call GitHub's delete ref (branch) API

        Args:
            branch_name (str): The name of the branch to delete

        Returns:

        Raises:
            RequestFailed: If the response fails validation.
        """
        path = "repos/{{org}}/{{repo}}/git/refs/heads/{ref}"\
            .format(ref=branch_name)
        return self._delete(path)

    def create_branch(self, branch_name, sha):
        """
        Calls GitHub's create ref (branch) API

        Arguments:
            branch_name (string): The name of the branch to create
            sha (string): The commit to base the branch off of

        Returns:

        Raises:
            RequestFailed: If the response fails validation.
        """
        path = "repos/{org}/{repo}/git/refs"
        payload = {
            "ref": "refs/heads/%s" % branch_name,
            "sha": sha
        }
        return self._post(path, payload)

    def create_pull_request(
            self,
            branch_name,
            base="release",
            title="",
            body=""):
        """ Creates a new pull request from a branch """
        path = "repos/{org}/{repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": branch_name,
            "base": base
        }
        return self._post(path, payload)
