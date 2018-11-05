"""
Tests for the Sailthru API functionality
"""
import logging
import mock
import pytest

from tubular.sailthru_api import SailthruApi
from sailthru.sailthru_error import SailthruClientError


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
        sailthru_api = SailthruApi('key', 'secret')
        sailthru_api._sailthru_client.api_delete.side_effect = SailthruClientError()  # pylint: disable=protected-access
        with pytest.raises(Exception) as exc:
            sailthru_api.delete_user(test_learner)
        assert 'Exception attempting to delete user foo@bar.com from Sailthru' in str(exc)


def test_sailthru_delete_not_ok_response(test_learner):  # pylint: disable=redefined-outer-name
    with mock.patch('tubular.sailthru_api.SailthruClient'):
        sailthru_api = SailthruApi('key', 'secret')
        mock_response = mock.Mock()
        mock_response.is_ok.return_value = False
        mock_error = mock.Mock()
        mock_error.get_message.return_value = "Random error message, doesnt matter what this is."
        mock_response.get_error.return_value = mock_error
        sailthru_api._sailthru_client.api_delete.return_value = mock_response  # pylint: disable=protected-access
        with pytest.raises(Exception) as exc:
            sailthru_api.delete_user(test_learner)
        assert 'Error attempting to delete user foo@bar.com from Sailthru' in str(exc)


def test_sailthru_delete_not_found_response(test_learner, caplog):  # pylint: disable=redefined-outer-name
    """
    The user never opted into email marketing, so they never had a sailthru
    profile generated.  Sailthru will respond with a "not found" error, which
    we should treat as "no action needed".
    """
    with mock.patch('tubular.sailthru_api.SailthruClient'):
        sailthru_api = SailthruApi('key', 'secret')
        mock_response = mock.Mock()
        mock_response.is_ok.return_value = False
        mock_error = mock.Mock()
        mock_error.get_message.return_value = 'User not found with email: foo@bar.com'
        mock_response.get_error.return_value = mock_error
        sailthru_api._sailthru_client.api_delete.return_value = mock_response  # pylint: disable=protected-access
        with caplog.at_level(logging.INFO):
            sailthru_api.delete_user(test_learner)
        assert 'No action taken because no profile was found - User not found with email: foo@bar.com' in caplog.text


@mock.patch('tubular.sailthru_api.log')
def test_sailthru_success(mock_logger, test_learner):  # pylint: disable=redefined-outer-name
    with mock.patch('tubular.sailthru_api.SailthruClient'):
        sailthru_api = SailthruApi('key', 'secret')
        mock_response = mock.Mock()
        mock_response.is_ok.return_value = True
        sailthru_api._sailthru_client.api_delete.return_value = mock_response  # pylint: disable=protected-access
        sailthru_api.delete_user(test_learner)
        mock_logger.info.assert_called_with('Email address %s successfully deleted from Sailthru.', 'foo@bar.com')
