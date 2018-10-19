"""
Tests for the Segment API functionality
"""
import mock

from tubular.segment_api import SegmentApi, SUPPRESS_MUTATION


class FakeResponse(object):
    """
    Fakes out requests.post response
    """
    def json(self):
        """
        Returns fake Segment retirement response data in the correct format
        """
        return {'data': {'createWorkspaceRegulation': {'id': 1}}}


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
    learner = {'id': 1, 'ecommerce_id': 'ecommerce-20', 'original_username': 'test_user'}
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

            assert mock_get_auth_token.call_count == len(projects_to_retire) * len(learner)
            assert mock_post.call_count == len(projects_to_retire) * len(learner)

            for proj in projects_to_retire:
                for curr_key in learner:
                    curr_id = learner[curr_key]
                    fake_json = {'query': SUPPRESS_MUTATION.format(fake_workspace, proj, curr_id)}
                    mock_post.assert_any_call(fake_base_url, json=fake_json, headers=headers)
