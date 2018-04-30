"""
Tests for edX API calls.
"""
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import unittest
from mock import patch

import tubular.edx_api as edx_api


class TestBaseApiClient(unittest.TestCase):
    """
    Test the edX base API client.
    """
    def test_get_access_token(self):
        """
        Test the get_access_token method.
        """
        with patch('tubular.edx_api.EdxRestApiClient.get_oauth_access_token') as mock:
            edx_api.BaseApiClient.get_access_token(
                'http://localhost',
                'the_client_id',
                'the_client_secret'
            )
            mock.assert_called_once_with(
                'http://localhost/oauth2/access_token',
                'the_client_id',
                'the_client_secret',
                token_type='jwt'
            )

    def test_base_api_client_client(self):
        """
        Test that the EdxRestApiClient is constructed properly.
        """
        with patch('tubular.edx_api.BaseApiClient.get_access_token') as mock:
            mock.return_value = ('THIS_IS_A_JWT', None)
            with patch('tubular.edx_api.EdxRestApiClient') as mock_client:
                edx_api.BaseApiClient(
                    'http://localhost:18000',
                    'http://localhost',
                    'the_client_id',
                    'the_client_secret'
                )
                mock_client.assert_called_once_with('http://localhost', jwt='THIS_IS_A_JWT', append_slash=True)


class TestLmsApi(unittest.TestCase):
    """
    Test the edX LMS API client.
    """
    def test_retrieve_learner_queue(self):
        with patch('tubular.edx_api.BaseApiClient.get_access_token') as mock:
            mock.return_value = ('THIS_IS_A_JWT', None)
            with patch('tubular.edx_api.EdxRestApiClient'):
                lms_api = edx_api.LmsApi(
                    'http://localhost:18000',
                    'http://localhost',
                    'the_client_id',
                    'the_client_secret'
                )
                lms_api.learners_to_retire(cool_off_days=365)
                # pylint: disable=protected-access
                lms_api._client.api.user.v1.accounts.retirement_queue.get.assert_called_once_with(
                    cool_off_days=365,
                    states=[
                        'PENDING',
                        'LOCKING_COMPLETE',
                        'CREDENTIALS_COMPLETE',
                        'ECOM_COMPLETE',
                        'FORUMS_COMPLETE',
                        'EMAIL_LISTS_COMPLETE',
                        'ENROLLMENTS_COMPLETE',
                        'NOTES_COMPLETE',
                        'PARTNERS_NOTIFIED',
                        'LMS_COMPLETE',
                    ]
                )
