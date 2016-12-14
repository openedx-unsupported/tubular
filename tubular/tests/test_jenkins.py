"""
Tests for triggering a Jenkins job.
"""
from __future__ import unicode_literals

import json
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
BUILD_NUM = 456
JOBS_URL = u'{}/job/{}/'.format(BASE_URL, JOB)
JOB_URL = u'{}{}'.format(JOBS_URL, BUILD_NUM)
MOCK_BUILD = {u'number': BUILD_NUM, u'url': JOB_URL}
MOCK_JENKINS_DATA = {'jobs': [{'name': JOB, 'url': JOBS_URL, 'color': 'blue'}]}
MOCK_BUILDS_DATA = {
    'actions': [
        {'parameterDefinitions': [
            {'defaultParameterValue': {'value': '0'}, 'name': 'EXIT_CODE', 'type': 'StringParameterDefinition'}
        ]}
    ],
    'builds': [MOCK_BUILD],
    'lastBuild': MOCK_BUILD
}
MOCK_QUEUE_DATA = {
    'id': 123,
    'task': {'name': JOB, 'url': JOBS_URL},
    'executable': {'number': BUILD_NUM, 'url': JOB_URL}
}
MOCK_BUILD_DATA = {
    'actions': [{}],
    'fullDisplayName': 'foo',
    'number': BUILD_NUM,
    'result': 'SUCCESS',
    'url': JOB_URL,
}


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
        (None, ()),
        ('my cause', ()),
        (None, ((u'FOO', u'bar'),)),
        (None, ((u'FOO', u'bar'), (u'BAZ', u'biz'))),
        ('my cause', ((u'FOO', u'bar'),)),
    )
    @ddt.unpack
    @httpretty.activate
    def test_success(self, cause, param):
        u"""
        Test triggering a jenkins job
        """
        def request_callback(_request, uri, headers):
            u""" What to return from the mock. """
            # This is the initial call that jenkinsapi uses to
            # establish connectivity to Jenkins
            # https://test-jenkins/api/python?tree=jobs[name,color,url]
            code = 200
            if uri.startswith(u'https://test-jenkins/api/python'):
                response = json.dumps(MOCK_JENKINS_DATA)
            elif uri.startswith(u'https://test-jenkins/job/test-job/456'):
                response = json.dumps(MOCK_BUILD_DATA)
            elif uri.startswith(u'https://test-jenkins/job/test-job'):
                response = json.dumps(MOCK_BUILDS_DATA)
            elif uri.startswith(u'https://test-jenkins/queue/item/123/api/python'):
                response = json.dumps(MOCK_QUEUE_DATA)
            else:
                # We should never get here, unless the jenkinsapi implementation changes.
                # This response will catch that condition.
                code = 500
                response = None
            return (code, headers, response)

        # Mock all network interactions
        httpretty.HTTPretty.allow_net_connect = False
        httpretty.register_uri(
            httpretty.GET,
            re.compile('.*'),
            body=request_callback
        )
        httpretty.register_uri(
            httpretty.POST,
            '{}/job/test-job/buildWithParameters'.format(BASE_URL),
            status=201,  # Jenkins responds with a 201 Created on success
            adding_headers={'location': '{}/queue/item/123'.format(BASE_URL)}
        )

        # Make the call to the Jenkins API
        result = jenkins.trigger_build(BASE_URL, USER_ID, USER_TOKEN, JOB, TOKEN, cause, param)
        self.assertEqual(result, 'SUCCESS')
