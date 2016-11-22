"""
Tests for triggering a Jenkins job.
"""
from __future__ import unicode_literals

import re
import unittest

import ddt
import httpretty

from tubular.exception import BackendError
import tubular.jenkins as jenkins

BASE_URL = u'https://test-jenkins'
USER_ID = u'foo'
USER_TOKEN = u'12345678901234567890123456789012'
JOB = u'test-job'
TOKEN = u'asdf'


@ddt.ddt
class TestJenkinsAPI(unittest.TestCase):
    """
    Tests for interacting with the Jenkins API
    """
    @httpretty.activate
    def test_failure(self):
        """
        Test the failure condition when triggering a jenkins job
        """
        # Mock all network interactions
        httpretty.HTTPretty.allow_net_connect = False
        httpretty.register_uri(
            httpretty.GET,
            re.compile(".*"),
            status=404,
        )
        with self.assertRaises(BackendError):
            jenkins.trigger_build(BASE_URL, USER_ID, USER_TOKEN, JOB, TOKEN, None, ())

    @ddt.data(
        (None, (), None),
        ('my cause', (), [u'cause=my+cause']),
        (None, ((u'FOO', u'bar'),), [u'FOO=bar']),
        (None, ((u'FOO', u'bar'), (u'BAZ', u'biz')), [u'FOO=bar', u'BAZ=biz']),
        ('my cause', ((u'FOO', u'bar'),), [u'cause=my+cause', u'FOO=bar']),
    )
    @ddt.unpack
    @httpretty.activate
    def test_success(self, cause, param, expected_query):
        """
        Test triggering a jenkins job
        """
        # Mock all network interactions
        httpretty.HTTPretty.allow_net_connect = False
        httpretty.register_uri(
            httpretty.GET,
            re.compile(".*"),
            status=201,  # Jenkins responds with a 201 Created on success
        )

        if param:
            expected_path = u'/job/{}/buildWithParameters'.format(JOB)
        else:
            expected_path = u'/job/{}/build'.format(JOB)

        # Make the call to the Jenkins API
        response = jenkins.trigger_build(BASE_URL, USER_ID, USER_TOKEN, JOB, TOKEN, cause, param)

        # We will check that the path and the query params were added correctly
        path_url = response.request.path_url
        url_parts = path_url.split('?')
        path = url_parts[0]
        query_string = url_parts[1]

        # Verify the URL path
        self.assertEqual(path, expected_path)

        # The token should always be passed to the job, as it is required
        actual_params = query_string.split('&')
        token_param = u'token={}'.format(TOKEN)
        self.assertIn(token_param, actual_params)
        actual_params.remove(token_param)

        # If you passed in a cause or some params, verify those
        if expected_query:
            for query in expected_query:
                self.assertIn(query, actual_params)
