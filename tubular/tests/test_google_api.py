"""
Test google API
"""

import json
import sys
import unittest
# Gives a version of zip which returns an iterable even under python 2.
from builtins import zip  # pylint: disable=redefined-builtin
from datetime import datetime, timedelta
from io import BytesIO
from itertools import cycle

import six
from googleapiclient.http import HttpMockSequence
from mock import patch
from pytz import UTC
from six.moves import range  # use the range function introduced in python 3

from tubular.google_api import BatchRequestError, DriveApi, FOLDER_MIMETYPE, GOOGLE_API_MAX_BATCH_SIZE

# For info about this file, see tubular/tests/discovery-drive.json.README.rst
DISCOVERY_DRIVE_RESPONSE_FILE = 'tubular/tests/discovery-drive.json'


class TestDriveApi(unittest.TestCase):
    """
    Test the DriveApi class.
    """
    maxDiff = None

    def setUp(self):
        super(TestDriveApi, self).setUp()
        with open(DISCOVERY_DRIVE_RESPONSE_FILE, 'r') as f:
            self.mock_discovery_response_content = f.read()

    @classmethod
    def _http_mock_sequence_retry(cls):
        """
        Returns a tuple, for use in http mock sequences, which represents a response from google suggesting to retry.
        """
        return (
            {'status': '403'},
            json.dumps({
                "error": {
                    "errors": [
                        {
                            "domain": "usageLimits",
                            "reason": "userRateLimitExceeded",
                            "message": "User Rate Limit Exceeded",
                        }
                    ],
                    "code": 403,
                    "message": "User Rate Limit Exceeded",
                }
            }).encode('utf-8'),
        )

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_create_file_success(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Test normal case for uploading a file.
        """
        fake_file_id = 'fake-file-id'
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            ({'status': '200'}, self.mock_discovery_response_content),
            # Then, a request is made to upload the file.
            ({'status': '200'}, '{{"id": "{}"}}'.format(fake_file_id)),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        response = test_client.create_file_in_folder(
            'fake-folder-id',
            'Fake Filename',
            BytesIO('fake file contents'.encode('ascii')),
            'text/plain',
        )
        assert response == fake_file_id

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    # pylint: disable=unused-argument
    def test_create_file_retry_success(self, mock_from_service_account_file):
        """
        Test rate limit and retry during file upload.
        """
        fake_file_id = 'fake-file-id'
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            ({'status': '200'}, self.mock_discovery_response_content),
            # Then, a request is made to upload the file while rate limiting was activated.  This should cause a retry.
            self._http_mock_sequence_retry(),
            # Finally, success.
            ({'status': '200'}, '{{"id": "{}"}}'.format(fake_file_id)),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        response = test_client.create_file_in_folder(
            'fake-folder-id',
            'Fake Filename',
            BytesIO('fake file contents'.encode('ascii')),
            'text/plain',
        )
        # There is no need to explicitly check if the call was retried because
        # the response value cannot possibly contain fake_file_id otherwise,
        # since it was only passed in the last response.
        assert response == fake_file_id

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_delete_file_success(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Test normal case for deleting files.
        """
        fake_file_ids = ['fake-file-id1', 'fake-file-id2']
        batch_response = b'''--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+0>

HTTP/1.1 204 OK
ETag: "etag/pony"\r\n\r\n

--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+1>

HTTP/1.1 204 OK
ETag: "etag/sheep"\r\n\r\n
--batch_foobarbaz--'''
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            ({'status': '200'}, self.mock_discovery_response_content),
            # Then, a request is made to delete files.
            ({'status': '200', 'content-type': 'multipart/mixed; boundary="batch_foobarbaz"'}, batch_response),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        if sys.version_info < (3, 4):
            # This is a simple smoke-test without checking the output because
            # python <3.4 doesn't support assertLogs.
            test_client.delete_files(fake_file_ids)
        else:
            # This is the full test case, which only runs under python 3.4+.
            with self.assertLogs(level='INFO') as captured_logs:  # pylint: disable=no-member
                test_client.delete_files(fake_file_ids)
            assert sum(
                'Successfully processed request' in msg
                for msg in captured_logs.output
            ) == 2

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_delete_file_with_nonexistent_file(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Test case for deleting files where some are nonexistent.
        """
        fake_file_id_non_existent = 'fake-file-id1'
        fake_file_id_exists = 'fake-file-id2'
        batch_response = b'''--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+0>

HTTP/1.1 404 NOT FOUND
Content-Type: application/json
Content-length: 266
ETag: "etag/pony"\r\n\r\n{
 "error": {
  "errors": [
   {
    "domain": "global",
    "reason": "notFound",
    "message": "File not found: fake-file-id1.",
    "locationType": "parameter",
    "location": "fileId"
   }
  ],
  "code": 404,
  "message": "File not found: fake-file-id1."
 }
}

--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+1>

HTTP/1.1 204 OK
ETag: "etag/sheep"\r\n\r\n
--batch_foobarbaz--'''
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            ({'status': '200'}, self.mock_discovery_response_content),
            # Then, a request is made to delete files.
            ({'status': '200', 'content-type': 'multipart/mixed; boundary="batch_foobarbaz"'}, batch_response),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        if sys.version_info < (3, 4):
            # This is a simple smoke-test without checking the output because
            # python 2 doesn't support assertLogs.
            with self.assertRaises(BatchRequestError):
                test_client.delete_files([fake_file_id_non_existent, fake_file_id_exists])
        else:
            # This is the full test case, which only runs under python 3.
            with self.assertLogs(level='INFO') as captured_logs:  # pylint: disable=no-member
                with self.assertRaises(BatchRequestError):
                    test_client.delete_files([fake_file_id_non_existent, fake_file_id_exists])
            assert sum('Error processing request' in msg for msg in captured_logs.output) == 1
            assert sum('Successfully processed request' in msg for msg in captured_logs.output) == 1

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_delete_files_older_than(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Tests the logic to delete files older than a certain age.
        """
        five_days_ago = datetime.now(UTC) - timedelta(days=5)
        fake_newish_files = [
            {
                'id': 'fake-text-file-id-{}'.format(idx),
                'createdTime': five_days_ago + timedelta(days=1),
                'mimeType': 'text/plain'
            }
            for idx in range(1, 10, 2)
        ]
        fake_old_files = [
            {
                'id': 'fake-text-file-id-{}'.format(idx),
                'createdTime': five_days_ago - timedelta(days=14),
                'mimeType': 'text/plain'
            }
            for idx in range(2, 10, 2)
        ]
        fake_files = fake_newish_files + fake_old_files
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            (
                {'status': '200'},
                self.mock_discovery_response_content,
            ),
            # Then, a request is made to list files.
            (
                {'status': '200', 'content-type': 'application/json'},
                json.dumps({'files': fake_files}, default=lambda x: x.isoformat()).encode('utf-8'),
            ),
        ])
        with patch.object(DriveApi, 'delete_files', return_value=None) as mock_delete_files:
            test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
            test_client.delete_files_older_than('fake-folder-id', five_days_ago)
        # Verify that the correct files were requested to be deleted.
        mock_delete_files.assert_called_once_with(['fake-text-file-id-{}'.format(idx) for idx in range(2, 10, 2)])

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_walk_files_multi_page_all_types(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Files are searched for - and returned in two pages.
        """
        fake_folder = [
            {
                'id': 'fake-folder-id-0',
                'name': 'fake-folder-name-0',
                'mimeType': 'application/vnd.google-apps.folder'
            }
        ]
        fake_text_files = [
            {
                'id': 'fake-text-file-id-{}'.format(idx),
                'name': 'fake-text-file-name-{}'.format(idx),
                'mimeType': 'text/plain'
            }
            for idx in range(10)
        ]
        fake_csv_files = [
            {
                'id': 'fake-csv-file-id-{}'.format(idx),
                'name': 'fake-csv-file-name-{}'.format(idx),
                'mimeType': 'application/csv'
            }
            for idx in range(10)
        ]
        fake_files_part_1 = fake_folder + fake_text_files[:3] + fake_csv_files[:3]
        fake_files_part_2 = fake_text_files[3:7] + fake_csv_files[3:8]
        fake_files_part_3 = fake_text_files[7:] + fake_csv_files[8:]
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            (
                {'status': '200'},
                self.mock_discovery_response_content,
            ),
            # Then, a request is made to list files.  The response contains a single folder and other files.
            (
                {'status': '200', 'content-type': 'application/json'},
                json.dumps({'files': fake_files_part_1}).encode('utf-8'),
            ),
            # Then, a request is made to list files from the single found folder.
            # The response contains a nextPageToken indicating there are more pages.
            (
                {'status': '200', 'content-type': 'application/json'},
                json.dumps({'files': fake_files_part_2, 'nextPageToken': 'fake-next-page-token'}).encode('utf-8'),
            ),
            # Finally, another list request is made.  This time, no nextPageToken is present in the response,
            # indicating there are no more pages.
            (
                {'status': '200', 'content-type': 'application/json'},
                json.dumps({'files': fake_files_part_3}).encode('utf-8'),
            ),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        response = test_client.walk_files('fake-folder-id')
        # Remove all the mimeTypes for comparison purposes.
        del fake_folder[0]['mimeType']
        for fake_file in fake_text_files:
            del fake_file['mimeType']
        for fake_file in fake_csv_files:
            del fake_file['mimeType']
        six.assertCountEqual(self, response, fake_folder + fake_text_files + fake_csv_files)

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_walk_files_multi_page_csv_only(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Files are searched for - and returned in two pages.
        """
        fake_folder = [
            {
                'id': 'fake-folder-id-0',
                'name': 'fake-folder-name-0',
                'mimeType': 'application/vnd.google-apps.folder'
            }
        ]
        fake_csv_files = [
            {
                'id': 'fake-csv-file-id-{}'.format(idx),
                'name': 'fake-csv-file-name-{}'.format(idx),
                'mimeType': 'application/csv'
            }
            for idx in range(10)
        ]
        fake_files_part_1 = fake_folder + fake_csv_files[:3]
        fake_files_part_2 = fake_csv_files[3:8]
        fake_files_part_3 = fake_csv_files[8:]
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            (
                {'status': '200'},
                self.mock_discovery_response_content,
            ),
            # Then, a request is made to list files.  The response contains a single folder and other files.
            (
                {'status': '200', 'content-type': 'application/json'},
                json.dumps({'files': fake_files_part_1}).encode('utf-8'),
            ),
            # Then, a request is made to list files from the single found folder.
            # The response contains a nextPageToken indicating there are more pages.
            (
                {'status': '200', 'content-type': 'application/json'},
                json.dumps({'files': fake_files_part_2, 'nextPageToken': 'fake-next-page-token'}).encode('utf-8'),
            ),
            # Finally, another list request is made.  This time, no nextPageToken is present in the response,
            # indicating there are no more pages.
            (
                {'status': '200', 'content-type': 'application/json'},
                json.dumps({'files': fake_files_part_3}).encode('utf-8'),
            ),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        response = test_client.walk_files('fake-folder-id', mimetype='application/csv')
        # Remove all the mimeTypes for comparison purposes.
        for fake_file in fake_csv_files:
            del fake_file['mimeType']
        six.assertCountEqual(self, response, fake_csv_files)

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_walk_files_one_page(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Simple case where subfolders are requested, and the response contains one page.
        """
        fake_folders = [
            {
                'id': 'fake-folder-id-{}'.format(idx),
                'name': 'fake-folder-name-{}'.format(idx),
                'mimeType': 'application/vnd.google-apps.folder'
            }
            for idx in range(10)
        ]
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            (
                {'status': '200'},
                self.mock_discovery_response_content,
            ),
            # Then, a request is made to list files.
            (
                {'status': '200', 'content-type': 'application/json'},
                json.dumps({'files': fake_folders}).encode('utf-8'),
            ),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        response = test_client.walk_files('fake-folder-id', mimetype=FOLDER_MIMETYPE, recurse=False)
        # Remove all the mimeTypes for comparison purposes.
        for fake_folder in fake_folders:
            del fake_folder['mimeType']
        six.assertCountEqual(self, response, fake_folders)

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_walk_files_two_page(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Subfolders are requested, but the response is paginated.
        """
        fake_folders = [
            {
                'id': 'fake-folder-id-{}'.format(idx),
                'name': 'fake-folder-name-{}'.format(idx),
                'mimeType': 'application/vnd.google-apps.folder'
            }
            for idx in range(10)
        ]
        fake_files_part_1 = fake_folders[:7]
        fake_files_part_2 = fake_folders[7:]
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            (
                {'status': '200'},
                self.mock_discovery_response_content,
            ),
            # Then, a request is made to list files.  The response contains a nextPageToken suggesting there are more
            # pages.
            (
                {'status': '200', 'content-type': 'application/json'},
                json.dumps({'files': fake_files_part_1, 'nextPageToken': 'fake-next-page-token'}).encode('utf-8'),
            ),
            # Finally, a second list request is made.  This time, no nextPageToken is present in the response,
            # suggesting there are no more pages.
            (
                {'status': '200', 'content-type': 'application/json'},
                json.dumps({'files': fake_files_part_2}).encode('utf-8'),
            ),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        response = test_client.walk_files('fake-folder-id', mimetype=FOLDER_MIMETYPE, recurse=False)
        # Remove all the mimeTypes for comparison purposes.
        for fake_folder in fake_folders:
            del fake_folder['mimeType']
        six.assertCountEqual(self, response, fake_folders)

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_walk_files_retry(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Subfolders are requested, but there is rate limiting causing a retry.
        """
        fake_folders = [
            {
                'id': 'fake-folder-id-{}'.format(idx),
                'name': 'fake-folder-name-{}'.format(idx),
                'mimeType': 'application/vnd.google-apps.folder'
            }
            for idx in range(10)
        ]
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            (
                {'status': '200'},
                self.mock_discovery_response_content),
            # Then, a request is made to list files, but the response suggests to retry.
            self._http_mock_sequence_retry(),
            # Finally, the request is retried, and the response is OK.
            (
                {'status': '200', 'content-type': 'application/json'},
                json.dumps({'files': fake_folders}).encode('utf-8'),
            ),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        response = test_client.walk_files('fake-folder-id', mimetype=FOLDER_MIMETYPE, recurse=False)
        # Remove all the mimeTypes for comparison purposes.
        for fake_folder in fake_folders:
            del fake_folder['mimeType']
        six.assertCountEqual(self, response, fake_folders)

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_comment_files_success(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Test normal case for commenting on files.
        """
        fake_file_ids = ['fake-file-id0', 'fake-file-id1']
        batch_response = b'''--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+0>

HTTP/1.1 204 OK
ETag: "etag/pony"\r\n\r\n{"id": "fake-comment-id0"}

--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+1>

HTTP/1.1 204 OK
ETag: "etag/sheep"\r\n\r\n{"id": "fake-comment-id1"}
--batch_foobarbaz--'''
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            ({'status': '200'}, self.mock_discovery_response_content),
            # Then, a request is made to add comments to the files.
            ({'status': '200', 'content-type': 'multipart/mixed; boundary="batch_foobarbaz"'}, batch_response),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        resp = test_client.create_comments_for_files(list(zip(fake_file_ids, cycle(['some comment message']))))
        six.assertCountEqual(
            self,
            resp,
            {
                'fake-file-id0': {'id': 'fake-comment-id0'},
                'fake-file-id1': {'id': 'fake-comment-id1'},
            },
        )

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_comment_files_batching_retries(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Test commenting on more files than the google API batch limit.  This also tests the partial retry
        mechanism when a subset of responses are rate limited.
        """
        num_files = int(GOOGLE_API_MAX_BATCH_SIZE * 1.5)
        fake_file_ids = ['fake-file-id{}'.format(n) for n in range(num_files)]
        batch_response_0 = '\n'.join(
            '''--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+{idx}>

HTTP/1.1 204 OK
ETag: "etag/pony{idx}"\r\n\r\n{{"id": "fake-comment-id{idx}"}}
'''.format(idx=n)
            for n in range(GOOGLE_API_MAX_BATCH_SIZE)
        )
        batch_response_0 += '--batch_foobarbaz--'
        batch_response_1 = '\n'.join(
            '''--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+{idx}>

HTTP/1.1 204 OK
ETag: "etag/pony{idx}"\r\n\r\n{{"id": "fake-comment-id{idx}"}}
'''.format(idx=n)
            for n in range(int(GOOGLE_API_MAX_BATCH_SIZE * 0.25))
        )
        batch_response_1 += '\n'
        batch_response_1 += '\n'.join(
            '''--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+{idx}>

HTTP/1.1 500 Internal Server Error
ETag: "etag/pony{idx}"\r\n\r\n
'''.format(idx=n)
            for n in range(int(GOOGLE_API_MAX_BATCH_SIZE * 0.25), int(GOOGLE_API_MAX_BATCH_SIZE * 0.5))
        )
        batch_response_1 += '--batch_foobarbaz--'
        batch_response_2 = '\n'.join(
            '''--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+{idx}>

HTTP/1.1 204 OK
ETag: "etag/pony{idx}"\r\n\r\n{{"id": "fake-comment-id{idx}"}}
'''.format(idx=n)
            for n in range(int(GOOGLE_API_MAX_BATCH_SIZE * 0.25), int(GOOGLE_API_MAX_BATCH_SIZE * 0.5))
        )
        batch_response_2 += '--batch_foobarbaz--'
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            ({'status': '200'}, self.mock_discovery_response_content),
            # Then, a request is made to add comments to the files, first batch. Return max batch size results.
            ({'status': '200', 'content-type': 'multipart/mixed; boundary="batch_foobarbaz"'}, batch_response_0),
            # Then, a request is made to add comments to the files, second batch. Only half of the results are returned,
            # the rest resulted in HTTP 500.
            ({'status': '200', 'content-type': 'multipart/mixed; boundary="batch_foobarbaz"'}, batch_response_1),
            # Then, a request is made retry the last half of the second batch (only the ones that returned the 500s).
            # Return the last 1/4 results.
            ({'status': '200', 'content-type': 'multipart/mixed; boundary="batch_foobarbaz"'}, batch_response_2),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        resp = test_client.create_comments_for_files(list(zip(fake_file_ids, cycle(['some comment message']))))
        six.assertCountEqual(
            self,
            resp,
            {
                'fake-file-id{}'.format(n): {'id': 'fake-comment-id{}'.format(n)}
                for n in range(num_files)
            },
        )

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_comment_files_with_nonexistent_file(self,
                                                 mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Test case for commenting on files, where some files are nonexistent.
        """
        fake_file_ids = ['fake-file-id0', 'fake-file-id1']
        batch_response = b'''--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+0>

HTTP/1.1 404 NOT FOUND
Content-Type: application/json
Content-length: 266
ETag: "etag/pony"\r\n\r\n{
 "error": {
  "errors": [
   {
    "domain": "global",
    "reason": "notFound",
    "message": "File not found: fake-file-id0.",
    "locationType": "parameter",
    "location": "fileId"
   }
  ],
  "code": 404,
  "message": "File not found: fake-file-id0."
 }
}

--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+1>

HTTP/1.1 204 OK
ETag: "etag/sheep"\r\n\r\n{"id": "fake-comment-id1"}
--batch_foobarbaz--'''
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            ({'status': '200'}, self.mock_discovery_response_content),
            # Then, a request is made to add comments to the files.
            ({'status': '200', 'content-type': 'multipart/mixed; boundary="batch_foobarbaz"'}, batch_response),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        if sys.version_info < (3, 4):
            # This is a simple smoke-test without checking the output because python <3.4 doesn't support assertLogs.
            with self.assertRaises(BatchRequestError):
                test_client.create_comments_for_files(list(zip(fake_file_ids, cycle(['some comment message']))))
        else:
            # This is the full test case, which only runs under python 3.4+.
            with self.assertLogs(level='INFO') as captured_logs:  # pylint: disable=no-member
                with self.assertRaises(BatchRequestError):
                    test_client.create_comments_for_files(list(zip(fake_file_ids, cycle(['some comment message']))))
            assert sum('Successfully processed request' in msg for msg in captured_logs.output) == 1
            assert sum('Error processing request' in msg for msg in captured_logs.output) == 1

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_comment_files_with_duplicate_file(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Test case for duplicate file IDs.
        """
        fake_file_ids = ['fake-file-id0', 'fake-file-id1', 'fake-file-id0']
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            ({'status': '200'}, self.mock_discovery_response_content),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        with self.assertRaises(ValueError):
            test_client.create_comments_for_files(list(zip(fake_file_ids, cycle(['some comment message']))))

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_list_permissions_success(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Test normal case for listing permissions on files.
        """
        fake_file_ids = ['fake-file-id0', 'fake-file-id1']
        batch_response = b'''--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+0>

HTTP/1.1 200 OK
Content-Type: application/json
ETag: "etag/pony"\r\n\r\n{"permissions": [{"emailAddress": "reader@example.com", "role": "reader"}]}

--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+1>

HTTP/1.1 200 OK
Content-Type: application/json
ETag: "etag/sheep"\r\n\r\n{"permissions": [{"emailAddress": "writer@example.com", "role": "writer"}]}
--batch_foobarbaz--'''
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            ({'status': '200'}, self.mock_discovery_response_content),
            # Then, a request is made to add comments to the files.
            ({'status': '200', 'content-type': 'multipart/mixed; boundary="batch_foobarbaz"'}, batch_response),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)
        resp = test_client.list_permissions_for_files(fake_file_ids)
        six.assertCountEqual(
            self,
            resp,
            {
                'fake-file-id0': [{'emailAddress': 'reader@example.com', 'role': 'reader'}],
                'fake-file-id1': [{'emailAddress': 'writer@example.com', 'role': 'writer'}],
            },
        )

    @patch('tubular.google_api.service_account.Credentials.from_service_account_file', return_value=None)
    def test_list_permissions_one_failure(self, mock_from_service_account_file):  # pylint: disable=unused-argument
        """
        Test case for listing permissions on files, but one file doesn't exist.
        """
        fake_file_ids = ['fake-file-id0', 'fake-file-id1', 'fake-file-id2']
        batch_response = b'''--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+0>

HTTP/1.1 200 OK
Content-Type: application/json
ETag: "etag/pony"\r\n\r\n{"permissions": [{"emailAddress": "reader@example.com", "role": "reader"}]}

--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+1>

HTTP/1.1 200 OK
Content-Type: application/json
ETag: "etag/sheep"\r\n\r\n{"permissions": [{"emailAddress": "writer@example.com", "role": "writer"}]}

--batch_foobarbaz
Content-Type: application/http
Content-Transfer-Encoding: binary
Content-ID: <response+2>

HTTP/1.1 404 NOT FOUND
Content-Type: application/json
Content-length: 266
ETag: "etag/bird"\r\n\r\n{
 "error": {
  "errors": [
   {
    "domain": "global",
    "reason": "notFound",
    "message": "File not found: fake-file-id2.",
    "locationType": "parameter",
    "location": "fileId"
   }
  ],
  "code": 404,
  "message": "File not found: fake-file-id2."
 }
}
--batch_foobarbaz--'''
        http_mock_sequence = HttpMockSequence([
            # First, a request is made to the discovery API to construct a client object for Drive.
            ({'status': '200'}, self.mock_discovery_response_content),
            # Then, a request is made to add comments to the files.
            ({'status': '200', 'content-type': 'multipart/mixed; boundary="batch_foobarbaz"'}, batch_response),
        ])
        test_client = DriveApi('non-existent-secrets.json', http=http_mock_sequence)

        if sys.version_info < (3, 4):
            # This is a simple smoke-test without checking the output because python <3.4 doesn't support assertLogs.
            with self.assertRaises(BatchRequestError):
                test_client.list_permissions_for_files(fake_file_ids)
        else:
            # This is the full test case, which only runs under python 3.4+.
            with self.assertLogs(level='INFO') as captured_logs:  # pylint: disable=no-member
                with self.assertRaises(BatchRequestError):
                    test_client.list_permissions_for_files(fake_file_ids)
            assert sum('Successfully processed request' in msg for msg in captured_logs.output) == 2
            assert sum('Error processing request' in msg for msg in captured_logs.output) == 1
