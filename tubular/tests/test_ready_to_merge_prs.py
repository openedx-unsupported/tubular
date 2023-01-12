"""
Tests of the code to get open prs with label 'Ready to merge'
"""
import json
import unittest
from unittest import mock

from tubular.scripts.get_ready_to_merge_prs import get_github_api_response


class TestReadyToMergePRS(unittest.TestCase):
    """
    Tests cases for open prs with label 'Ready to merge'
    """
    def setUp(self):
        super().setUp()
        self.content = {
            "total_count": 1,
            "incomplete_results": "false",
            "items": [
                {
                    "url": "https://api.github.com/repos/openedx/edx-toggles/issues/246",
                    "repository_url": "https://api.github.com/repos/openedx/edx-toggles",
                    "labels_url": "https://api.github.com/repos/openedx/edx-toggles/issues/246/labels{/name}",
                    "comments_url": "https://api.github.com/repos/openedx/edx-toggles/issues/246/comments",
                    "html_url": "https://github.com/openedx/edx-platform/pull/300001",
                },
                {
                    "url": "https://api.github.com/repos/openedx/edx-toggles/issues/246",
                    "repository_url": "https://api.github.com/repos/openedx/edx-toggles",
                    "labels_url": "https://api.github.com/repos/openedx/edx-toggles/issues/246/labels{/name}",
                    "comments_url": "https://api.github.com/repos/openedx/edx-toggles/issues/246/comments",
                    "html_url": "https://github.com/openedx/edx-toggles/pull/2001",
                }]
        }

    def _mock_response(self, status=200, json_data=None, raise_for_status=None):
        """
        mock the response.
        """
        mock_resp = mock.Mock()
        mock_resp.raise_for_status = mock.Mock()
        if raise_for_status:
            mock_resp.raise_for_status.side_effect = raise_for_status

        mock_resp.status_code = status

        mock_resp.json = mock.Mock(return_value=json_data)
        return mock_resp

    @mock.patch('requests.get')
    def test_apis(self, mock_get):
        """ verify method returns the valid pr links """
        mock_resp = self._mock_response(json_data=self.content)
        mock_get.return_value = mock_resp
        content = get_github_api_response('openedx', '12345')
        expected = [item['html_url'] for item in self.content['items']]
        self.assertEqual(json.dumps(expected), content)

    @mock.patch('requests.get')
    def test_apis_without_records(self, mock_get):
        """ verify code works in case of no results """
        mock_resp = self._mock_response(json_data={'total_count': 0, 'incomplete_results': False, 'items': []})
        mock_get.return_value = mock_resp
        content = get_github_api_response('openedx', '12345')
        self.assertEqual(json.dumps([]), content)

    def test_apis_with_errors(self):
        """ test in case of exception"""
        with mock.patch('tubular.scripts.get_ready_to_merge_prs.requests.get', side_effect=Exception("error")):
            get_github_api_response('openedx', '12345')
