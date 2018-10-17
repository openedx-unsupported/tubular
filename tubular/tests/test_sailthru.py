"""
Tests for the Sailthru API functionality
"""
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
        sailthru_api._sailthru_client.api_delete.return_value = mock_response  # pylint: disable=protected-access
        with pytest.raises(Exception) as exc:
            sailthru_api.delete_user(test_learner)
        assert 'Error attempting to delete user foo@bar.com from Sailthru' in str(exc)


@mock.patch('tubular.sailthru_api.log')
def test_sailthru_success(mock_logger, test_learner):  # pylint: disable=redefined-outer-name
    with mock.patch('tubular.sailthru_api.SailthruClient'):
        sailthru_api = SailthruApi('key', 'secret')
        mock_response = mock.Mock()
        mock_response.is_ok.return_value = True
        sailthru_api._sailthru_client.api_delete.return_value = mock_response  # pylint: disable=protected-access
        sailthru_api.delete_user(test_learner)
        mock_logger.info.assert_called_with('Email address %s successfully deleted from Sailthru.', 'foo@bar.com')
