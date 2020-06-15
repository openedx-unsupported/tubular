"""
Tests for edX API calls.
"""

import unittest

import requests
from ddt import ddt, data
from mock import patch
from slumber.exceptions import HttpServerError

import tubular.edx_api as edx_api
from tubular.tests.retirement_helpers import TEST_RETIREMENT_QUEUE_STATES


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
                mock_client.assert_called_once_with(
                    'http://localhost',
                    jwt='THIS_IS_A_JWT',
                    append_slash=True
                )


class BackoffTriedException(Exception):
    """
    Raise this from a backoff handler to indicate that backoff was tried.
    """


@ddt
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
                lms_api.learners_to_retire(TEST_RETIREMENT_QUEUE_STATES, cool_off_days=365)
                # pylint: disable=protected-access
                lms_api._client.api.user.v1.accounts.retirement_queue.get.assert_called_once_with(
                    cool_off_days=365,
                    states=TEST_RETIREMENT_QUEUE_STATES
                )

    @data(504, 500)
    @patch('tubular.edx_api._backoff_handler')
    def test_retrieve_learner_queue_backoff(self, svr_status_code, mock_backoff_handler):
        mock_backoff_handler.side_effect = BackoffTriedException
        with patch('tubular.edx_api.BaseApiClient.get_access_token') as mock_get_access_token:
            mock_get_access_token.return_value = ('THIS_IS_A_JWT', None)
            with patch('tubular.edx_api.EdxRestApiClient'):
                lms_api = edx_api.LmsApi(
                    'http://localhost:18000',
                    'http://localhost',
                    'the_client_id',
                    'the_client_secret'
                )
                response = requests.Response()
                response.status_code = svr_status_code
                # pylint: disable=protected-access
                lms_api._client.api.user.v1.accounts.retirement_queue.get.side_effect = \
                    HttpServerError(response=response)
                with self.assertRaises(BackoffTriedException):
                    lms_api.learners_to_retire(TEST_RETIREMENT_QUEUE_STATES, cool_off_days=365)
