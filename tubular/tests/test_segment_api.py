"""
Tests for the Segment API functionality
"""
import json
import mock
import pytest
from simplejson.errors import JSONDecodeError

import requests
from six import text_type

from tubular.segment_api import SegmentApi, BULK_DELETE_STATUS_URL, BULK_DELETE_URL


FAKE_AUTH_TOKEN = 'FakeToken'
TEST_SEGMENT_CONFIG = {
    'projects_to_retire': ['project_1', 'project_2'],
    'learner': [{'id': 1, 'ecommerce_segment_id': 'ecommerce-20', 'original_username': 'test_user'}],
    'fake_base_url': 'https://segment.invalid/',
    'fake_auth_token': FAKE_AUTH_TOKEN,
    'fake_workspace': 'FakeEdx',
    'headers': {"Authorization": "Bearer {}".format(FAKE_AUTH_TOKEN), "Content-Type": "application/json"}
}


class FakeResponse(object):
    """
    Fakes out requests.post response
    """
    def json(self):
        """
        Returns fake Segment retirement response data in the correct format
        """
        return {'regulate_id': 1}

    def raise_for_status(self):
        pass


class FakeErrorResponse(object):
    """
    Fakes an error response
    """
    status_code = 500
    text = "{'error': 'Test error message'}"

    def json(self):
        """
        Returns fake Segment retirement response error in the correct format
        """
        return json.loads(self.text)

    def raise_for_status(self):
        raise requests.exceptions.HTTPError("", response=self)



@pytest.fixture
def setup_bulk_delete():
    """
    Fixture to setup common bulk delete items.
    """
    with mock.patch('requests.post') as mock_post:
        segment = SegmentApi(
            *[TEST_SEGMENT_CONFIG[key] for key in [
                'fake_base_url', 'fake_auth_token', 'fake_workspace'
            ]]
        )

        yield mock_post, segment


def test_bulk_delete_success(setup_bulk_delete):  # pylint: disable=redefined-outer-name
    """
    Test simple success case
    """
    mock_post, segment = setup_bulk_delete
    mock_post.return_value = FakeResponse()

    learner = TEST_SEGMENT_CONFIG['learner']
    segment.delete_learners(learner, 1000)

    assert mock_post.call_count == 1

    learners_vals = []
    for curr_key in ['id', 'original_username', 'ecommerce_segment_id']:
        curr_id = learner[0][curr_key]
        learners_vals.append(text_type(curr_id))

    fake_json = {
        "regulation_type": "Suppress_With_Delete",
        "attributes": {
            "name": "userId",
            "values": learners_vals
        }
    }

    url = TEST_SEGMENT_CONFIG['fake_base_url'] + BULK_DELETE_URL.format(TEST_SEGMENT_CONFIG['fake_workspace'])
    mock_post.assert_any_call(
        url, json=fake_json, headers=TEST_SEGMENT_CONFIG['headers']
    )


def test_bulk_delete_error(setup_bulk_delete, caplog):  # pylint: disable=redefined-outer-name
    """
    Test simple error case
    """
    mock_post, segment = setup_bulk_delete
    mock_post.return_value = FakeErrorResponse()

    learner = TEST_SEGMENT_CONFIG['learner']
    with pytest.raises(Exception):
        segment.delete_learners(learner, 1000)

    assert mock_post.call_count == 4
    assert "Error was encountered for learners between start/end indices (0, 0)" in caplog.text
    assert "{'error': 'Test error message'}" in caplog.text
