"""
Tests for the Sailthru API functionality
"""
import logging
import os

import mock
import pytest
from sailthru.sailthru_error import SailthruClientError
from six.moves import reload_module

# This module is imported separately solely so it can be re-loaded below.
from tubular import sailthru_api
# This SailthruApi class will be used without being re-loaded.
from tubular.sailthru_api import SailthruApi

# Change the number of retries for Sailthru API's delete_user call to 1.
# Then reload sailthru_api so only a single retry is performed.
os.environ['RETRY_SAILTHRU_MAX_ATTEMPTS'] = "1"
reload_module(sailthru_api)  # pylint: disable=too-many-function-args


@pytest.fixture
def test_learner():
    return {'original_email': 'foo@bar.com'}


def test_sailthru_delete_no_email():
    with mock.patch('tubular.sailthru_api.SailthruClient'):
        with pytest.raises(TypeError) as exc:
            SailthruApi('key', 'secret').delete_user({})
        assert 'Expected an email address for user to delete, but received None.' in str(exc)


def test_sailthru_delete_client_error(test_learner):  # pylint: disable=redefined-outer-name
    with mock.patch('tubular.sailthru_api.SailthruClient'):
        reloaded_sailthru_api = sailthru_api.SailthruApi('key', 'secret')  # pylint: disable=redefined-outer-name
        reloaded_sailthru_api._sailthru_client.api_delete.side_effect = SailthruClientError()  # pylint: disable=protected-access
        with pytest.raises(SailthruClientError):
            reloaded_sailthru_api.delete_user(test_learner)


def test_sailthru_delete_not_ok_response(test_learner):  # pylint: disable=redefined-outer-name
    with mock.patch('tubular.sailthru_api.SailthruClient'):
        sailthru_api = SailthruApi('key', 'secret')  # pylint: disable=redefined-outer-name
        mock_response = mock.Mock()
        mock_response.is_ok.return_value = False
        mock_error = mock.Mock()
        mock_error.get_message.return_value = "Random error message, doesnt matter what this is."
        mock_response.get_error.return_value = mock_error
        sailthru_api._sailthru_client.api_delete.return_value = mock_response  # pylint: disable=protected-access
        with pytest.raises(Exception) as exc:
            sailthru_api.delete_user(test_learner)
        assert 'Error attempting to delete user from Sailthru' in str(exc)


def test_sailthru_delete_not_found_response(test_learner, caplog):  # pylint: disable=redefined-outer-name
    """
    The user never opted into email marketing, so they never had a sailthru
    profile generated.  Sailthru will respond with a "not found" error, which
    we should treat as "no action needed".
    """
    with mock.patch('tubular.sailthru_api.SailthruClient'):
        sailthru_api = SailthruApi('key', 'secret')  # pylint: disable=redefined-outer-name
        mock_response = mock.Mock()
        mock_response.is_ok.return_value = False
        mock_error = mock.Mock()
        mock_error.get_message.return_value = 'User not found with email: foo@bar.com'
        mock_response.get_error.return_value = mock_error
        sailthru_api._sailthru_client.api_delete.return_value = mock_response  # pylint: disable=protected-access
        with caplog.at_level(logging.INFO):
            sailthru_api.delete_user(test_learner)
        assert 'No action taken because no user was found in Sailthru.' in caplog.text


def test_sailthru_success(test_learner, caplog):  # pylint: disable=redefined-outer-name
    with mock.patch('tubular.sailthru_api.SailthruClient'):
        sailthru_api = SailthruApi('key', 'secret')  # pylint: disable=redefined-outer-name
        mock_response = mock.Mock()
        mock_response.is_ok.return_value = True
        sailthru_api._sailthru_client.api_delete.return_value = mock_response  # pylint: disable=protected-access
        with caplog.at_level(logging.INFO):
            sailthru_api.delete_user(test_learner)
        assert 'User successfully deleted from Sailthru.' in caplog.text
