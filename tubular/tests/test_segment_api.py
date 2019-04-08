"""
Tests for the Segment API functionality
"""
import mock
import pytest

from tubular.segment_api import SegmentApi, BULK_DELETE_MUTATION, BULK_DELETE_MUTATION_OPNAME


FAKE_AUTH_TOKEN = 'FakeToken'
TEST_SEGMENT_CONFIG = {
    'projects_to_retire': ['project_1', 'project_2'],
    'learner': [{'id': 1, 'ecommerce_segment_id': 'ecommerce-20', 'original_username': 'test_user'}],
    'fake_base_url': 'https://segment.invalid',
    'fake_email': 'fake_email',
    'fake_password': 'fake_password',
    'fake_auth_token': FAKE_AUTH_TOKEN,
    'fake_workspace': 'FakeEdx',
    'headers': {"Authorization": "Bearer {}".format(FAKE_AUTH_TOKEN)}
}


class FakeResponse(object):
    """
    Fakes out requests.post response
    """
    def json(self):
        """
        Returns fake Segment retirement response data in the correct format
        """
        return {'data': {BULK_DELETE_MUTATION_OPNAME: {'id': 1}}}


class FakeErrorResponse(object):
    """
    Fakes an error response
    """
    def json(self):
        """
        Returns fake Segment retirement response error in the correct format
        """
        return {'error': 'Test error message'}


@pytest.fixture
def setup_bulk_delete():
    """
    Fixture to setup common bulk delete items.
    """
    with mock.patch('requests.post') as mock_post:
        with mock.patch('tubular.segment_api.SegmentApi._get_auth_token') as mock_get_auth_token:
            mock_get_auth_token.return_value = FAKE_AUTH_TOKEN

            segment = SegmentApi(
                *[TEST_SEGMENT_CONFIG[key] for key in [
                    'fake_base_url', 'fake_email', 'fake_password', 'fake_workspace'
                ]]
            )
            yield mock_post, segment

            assert mock_get_auth_token.call_count == 1


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
        learners_vals.append('"{}"'.format(curr_id))
    learners_str = '[' + ','.join(learners_vals) + ']'
    fake_json = {'query': BULK_DELETE_MUTATION.format(TEST_SEGMENT_CONFIG['fake_workspace'], learners_str)}
    mock_post.assert_any_call(
        TEST_SEGMENT_CONFIG['fake_base_url'], json=fake_json, headers=TEST_SEGMENT_CONFIG['headers'])


def test_bulk_delete_error(setup_bulk_delete, caplog):  # pylint: disable=redefined-outer-name
    """
    Test simple error case
    """
    mock_post, segment = setup_bulk_delete
    mock_post.return_value = FakeErrorResponse()

    learner = TEST_SEGMENT_CONFIG['learner']
    with pytest.raises(Exception):
        segment.delete_learners(learner, 1000)

    assert mock_post.call_count == 1
    assert "Error was encountered for learners between start/end indices (0, 0)" in caplog.text
    assert "{'error': 'Test error message'}" in caplog.text
