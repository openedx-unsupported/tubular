"""
Tests for testeng-ci/release/github_api
"""
from __future__ import unicode_literals

import json
from unittest import TestCase

import re
import ddt
import responses
from responses import GET, POST, DELETE  # pylint: disable=no-name-in-module
from tubular.github import RequestFailed, GithubApi


class Aborted(Exception):
    """
    Exception used to escape from operations that are being mocked
    or intercepted and should abort
    """
    pass


class EndpointInfo(object):
    # pylint: disable=too-few-public-methods
    """ Encapsulates the info we need to test an end point """

    def __init__(
            self,
            expected_url,
            request_maker,
            success=200,
            method=GET,
            request_body=None):  # pylint: disable=too-many-arguments
        self.expected_url = expected_url
        self.request_maker = request_maker
        self.success = success
        self.method = method
        self.request_body = request_body

ENDPOINTS = [
    EndpointInfo(
        "https://api.github.com/repos/test-org/test-repo/commits",
        lambda api: api.commits()
    ),
    EndpointInfo(
        "https://api.github.com/user",
        lambda api: api.user()
    ),
    EndpointInfo(
        "https://api.github.com/repos/test-org/test-repo/commits" +
        "/sample_hash/status",
        lambda api: api.commit_statuses('sample_hash')
    ),
    EndpointInfo(
        "https://api.github.com/repos/test-org/test-repo/git/refs",
        lambda api: api.create_branch('branch_name', 'sample_hash'),
        success=201,
        method=POST,
        request_body={'sha': 'sample_hash', 'ref': 'refs/heads/branch_name'}
    ),
    EndpointInfo(
        "https://api.github.com/repos/test-org/test-repo/pulls",
        lambda api: api.create_pull_request(
            'branch_name', 'base', title='some request', body='more text'
        ),
        success=201,
        method=POST,
        request_body={
            'body': 'more text', 'head': 'branch_name',
            'base': 'base', 'title': 'some request'
        }
    ),
    EndpointInfo(
        "https://api.github.com/" +
        "repos/test-org/test-repo/git/refs/heads/test-branch",
        lambda api: api.delete_branch('test-branch'),
        success=204,
        method=DELETE
    ),
]


@ddt.ddt
class GitHubApiTestCase(TestCase):
    """
    Tests the requests creation/response handling for the Github API
    All Network calls should be mocked out.
    """

    def setUp(self):
        self.api = GithubApi("test-org", "test-repo", token="abc123")
        self.catch_all_re = re.compile(r'.*')
        super(GitHubApiTestCase, self).setUp()

    def add_catch_all(self, rsps, method, status, body='{}'):
        """ Helper method for easily intercepting all network requests """
        rsps.add(
            method,
            self.catch_all_re,
            body=body,
            status=status,
            content_type='application/json'
        )

    def test_token_argument(self):
        """ Tests that the token argument is propagated. """
        self.assertEqual(self.api.token, "abc123")

    def verify_invalid_request(self, endpoint, verifier):
        """
        Helper function that makes a request that fails. Then allows an
        argument to verify the output of the failure.
        """
        with responses.RequestsMock() as rsps:
            self.add_catch_all(rsps, endpoint.method, status=404)
            with self.assertRaises(RequestFailed) as context:
                endpoint.request_maker(self.api)

            response = context.exception.response
            verifier(response)

    @ddt.data(*ENDPOINTS)
    def test_endpoint_url(self, endpoint):
        """ Tests that the api requests the correct url """

        def verifier(response):
            """ Helper to check for the expected url """
            self.assertEqual(response.url, endpoint.expected_url)
        self.verify_invalid_request(endpoint, verifier)

    @ddt.data(*ENDPOINTS)
    def test_endpoints_invalid(self, endpoint):
        """Tests that the api catches invalid responses"""

        def verifier(response):
            """ Helper to check for the expected status code """
            self.assertEqual(response.status_code, 404)
        self.verify_invalid_request(endpoint, verifier)

    @ddt.data(*ENDPOINTS)
    def test_request_body(self, endpoint):
        """ Tests that the API request body data matches expectations """
        def verifier(request):
            """ Tests that the API request body data matches expectations """
            if endpoint.request_body:
                body = json.loads(request.body)
                self.assertEqual(body, endpoint.request_body)
            raise Aborted(request)

        with responses.RequestsMock() as rsps:
            rsps.add_callback(
                endpoint.method,
                self.catch_all_re,
                callback=verifier,
                content_type='application/json'
            )
            try:
                endpoint.request_maker(self.api)
            except Aborted:
                # Verifier escapes via exception
                pass

    @ddt.data(*ENDPOINTS)
    def test_endpoints_valid(self, endpoint):
        """ Tests that the API propagates valid responses """
        with responses.RequestsMock() as rsps:
            body = '{"test": "ab"}'
            success = endpoint.success
            method = endpoint.method
            self.add_catch_all(rsps, method, status=success, body=body)
            result = endpoint.request_maker(self.api)
            self.assertEqual(result['test'], 'ab')
