"""
Tests for the Segment API functionality
"""
import mock

from tubular.segment_api import SegmentApi, BULK_DELETE_MUTATION, BULK_DELETE_MUTATION_OPNAME


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
    Fakes a response with the given error code
    """
    def __init__(self, status_code):
        self.status_code = status_code


def test_suppress_and_delete_success():
    """
    Test simple success case
    """
    projects_to_retire = ['project_1', 'project_2']
    learner = [{'id': 1, 'ecommerce_segment_id': 'ecommerce-20', 'original_username': 'test_user'}]
    fake_base_url = 'https://segment.invalid'
    fake_email = 'fake_email'
    fake_password = 'fake_password'
    fake_auth_token = 'FakeToken'
    fake_workspace = 'FakeEdx'
    headers = {"Authorization": "Bearer {}".format(fake_auth_token)}

    with mock.patch('requests.post') as mock_post:
        with mock.patch('tubular.segment_api.SegmentApi._get_auth_token') as mock_get_auth_token:
            mock_get_auth_token.return_value = fake_auth_token
            mock_post.return_value = FakeResponse()

            segment = SegmentApi(fake_base_url, fake_email, fake_password, projects_to_retire, fake_workspace)
            segment.suppress_and_delete(learner)

            assert mock_get_auth_token.call_count == len(learner)
            assert mock_post.call_count == len(learner)

            learners_vals = []
            for curr_key in ['id', 'original_username', 'ecommerce_segment_id']:
                curr_id = learner[0][curr_key]
                learners_vals.append('"{}"'.format(curr_id))
            learners_str = '[' + ','.join(learners_vals) + ']'
            fake_json = {'query': BULK_DELETE_MUTATION.format(fake_workspace, learners_str)}
            mock_post.assert_any_call(fake_base_url, json=fake_json, headers=headers)
