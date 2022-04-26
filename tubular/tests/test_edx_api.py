"""
Tests for edX API calls.
"""
import unittest

import requests
import responses
from ddt import data, ddt
from mock import patch
from requests.exceptions import ConnectionError, HTTPError
from responses import matchers

import tubular.edx_api as edx_api
from tubular.tests.mixins import OAuth2Mixin
from tubular.tests.retirement_helpers import TEST_RETIREMENT_QUEUE_STATES


class BackoffTriedException(Exception):
    """
    Raise this from a backoff handler to indicate that backoff was tried.
    """


@ddt
class TestLmsApi(OAuth2Mixin, unittest.TestCase):
    """
    Test the edX LMS API client.
    """

    @responses.activate
    @patch.object(edx_api.LmsApi, 'learners_to_retire')
    def test_retrieve_learner_queue(self, mock_learners_to_retire):
        self.mock_access_token_response()
        params = {
            'states': TEST_RETIREMENT_QUEUE_STATES,
            'cool_off_days': 365,
        }
        lms_api = edx_api.LmsApi(
            'http://localhost:18000',
            'http://localhost:18000',
            'the_client_id',
            'the_client_secret'
        )
        responses.add(
            responses.GET,
            'http://localhost:18000/api/user/v1/accounts/retirement_queue/',
            status=200,
            match=[matchers.query_param_matcher(params)],
        )
        lms_api.learners_to_retire(TEST_RETIREMENT_QUEUE_STATES, cool_off_days=365)
        mock_learners_to_retire.assert_called_once_with(TEST_RETIREMENT_QUEUE_STATES, cool_off_days=365)

    @responses.activate
    @data(504, 500)
    @patch('tubular.edx_api._backoff_handler')
    @patch.object(edx_api.LmsApi, 'learners_to_retire')
    def test_retrieve_learner_queue_backoff(
            self,
            svr_status_code,
            mock_backoff_handler,
            mock_learners_to_retire
    ):
        mock_backoff_handler.side_effect = BackoffTriedException
        self.mock_access_token_response()
        params = {
            'states': TEST_RETIREMENT_QUEUE_STATES,
            'cool_off_days': 365,
        }
        lms_api = edx_api.LmsApi(
            'http://localhost:18000',
            'http://localhost:18000',
            'the_client_id',
            'the_client_secret'
        )
        response = requests.Response()
        response.status_code = svr_status_code
        responses.add(
            responses.GET,
            'http://localhost:18000/api/user/v1/accounts/retirement_queue/',
            status=200,
            match=[matchers.query_param_matcher(params)],
        )

        mock_learners_to_retire.side_effect = HTTPError(response=response)
        with self.assertRaises(BackoffTriedException):
            lms_api.learners_to_retire(TEST_RETIREMENT_QUEUE_STATES, cool_off_days=365)

    @data(104)
    @responses.activate
    @patch('tubular.edx_api._backoff_handler')
    @patch.object(edx_api.LmsApi, 'retirement_partner_cleanup')
    def test_retirement_partner_cleanup_backoff_on_connection_error(
            self,
            svr_status_code,
            mock_backoff_handler,
            mock_retirement_partner_cleanup
    ):
        mock_backoff_handler.side_effect = BackoffTriedException
        self.mock_access_token_response()
        lms_api = edx_api.LmsApi(
            'http://localhost:18000',
            'http://localhost:18000',
            'the_client_id',
            'the_client_secret'
        )
        response = requests.Response()
        response.status_code = svr_status_code
        mock_retirement_partner_cleanup.retirement_partner_cleanup.side_effect = ConnectionError(response=response)
        with self.assertRaises(BackoffTriedException):
            lms_api.retirement_partner_cleanup([{'original_username': 'test'}])
