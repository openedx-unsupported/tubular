"""
Tests for the Braze API functionality
"""
import ddt
import os
import logging
import unittest
from unittest import mock

import requests_mock

os.environ['RETRY_BRAZE_MAX_ATTEMPTS'] = '2'
from tubular.braze_api import BrazeApi, BrazeException, BrazeRecoverableException


@ddt.ddt
@requests_mock.Mocker()
class TestBraze(unittest.TestCase):
    """
    Class containing tests of all code interacting with Braze.
    """
    def setUp(self):
        super().setUp()
        self.learner = {'user': {'id': 1234}}
        self.braze = BrazeApi('test-key', 'test-instance')

    def _mock_delete(self, req_mock, status_code, message=None):
        req_mock.post(
            'https://rest.test-instance.braze.com/users/delete',
            request_headers={'Authorization': 'Bearer test-key'},
            json={'message': message} if message else {},
            status_code=status_code
        )

    def test_delete_happy_path(self, req_mock):
        self._mock_delete(req_mock, 200)

        logger = logging.getLogger('tubular.braze_api')
        with mock.patch.object(logger, 'info') as mock_info:
            self.braze.delete_user(self.learner)

        self.assertEqual(mock_info.call_args, [('Braze user deletion succeeded',)])

        self.assertEqual(len(req_mock.request_history), 1)
        request = req_mock.request_history[0]
        self.assertEqual(request.json(), {'external_ids': [1234]})

    def test_delete_fatal_error(self, req_mock):
        self._mock_delete(req_mock, 404, message='Test Error Message')

        logger = logging.getLogger('tubular.braze_api')
        with mock.patch.object(logger, 'error') as mock_error:
            with self.assertRaises(BrazeException) as exc:
                self.braze.delete_user(self.learner)

        error = 'Braze user deletion failed due to Test Error Message'
        self.assertEqual(mock_error.call_args, [(error,)])
        self.assertEqual(str(exc.exception), error)

    @ddt.data(429, 500)
    def test_delete_recoverable_error(self, status_code, req_mock):
        self._mock_delete(req_mock, status_code)

        with self.assertRaises(BrazeRecoverableException):
            self.braze.delete_user(self.learner)

        self.assertEqual(len(req_mock.request_history), 2)
