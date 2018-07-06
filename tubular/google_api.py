"""
Helper API classes for calling google APIs.

DriveApi is for managing files in google drive.
"""
import logging

import backoff

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
# I'm not super happy about this since the function is protected with a leading
# underscore, but the next best thing is literally copying this ~40 line
# function verbatim.
from googleapiclient.http import _should_retry_response
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account

LOG = logging.getLogger(__name__)


class BaseApiClient(object):
    """
    Base API client for google services.

    To add a new service, extend this class and override these class variables:

      _api_name  (e.g. "drive")
      _api_version  (e.g. "v3")
      _api_scopes
    """
    _api_name = None
    _api_version = None
    _api_scopes = None

    def __init__(self, client_secrets_file_path, **kwargs):
        self.build_client(client_secrets_file_path, **kwargs)

    def build_client(self, client_secrets_file_path, **kwargs):
        """
        Build the google API client, specific to a single google service.
        """
        credentials = service_account.Credentials.from_service_account_file(
            client_secrets_file_path, scopes=self._api_scopes)
        self._client = build(self._api_name, self._api_version, credentials=credentials, **kwargs)


def _backoff_handler(details):
    """
    Simple logging handler for when timeout backoff occurs.
    """
    LOG.info('Trying again in {wait:0.1f} seconds after {tries} tries calling {target}'.format(**details))


def _should_retry_google_api(exc):
    """
    General logic for determining if a google API response is retryable.

    Args:
        exc (googleapiclient.errors.HttpError): The exception thrown by googleapiclient.

    Returns:
        bool: True if the caller should retry the API call.
    """
    retry = False
    if hasattr(exc, 'resp') and exc.resp:  # bizzare and disappointing that sometimes `resp` doesn't exist.
        retry = _should_retry_response(exc.resp.status, exc.content)
    return retry


class DriveApi(BaseApiClient):
    """
    Google Drive API client.
    """
    _api_name = 'drive'
    _api_version = 'v3'
    _api_scopes = [
        # basic file read-write functionality.
        'https://www.googleapis.com/auth/drive.file',
        # additional scope for being able to see folders not owned by this account.
        'https://www.googleapis.com/auth/drive.metadata',
    ]

    @backoff.on_exception(
        backoff.expo,
        HttpError,
        max_time=600,  # 10 minutes
        giveup=lambda e: not _should_retry_google_api(e),
        on_backoff=lambda details: _backoff_handler(details),  # pylint: disable=unnecessary-lambda
    )
    def create_file_in_folder(self, folder_id, filename, file_stream, mimetype):
        """
        Creates a new file in the specified folder.

        Args:
            folder_id (str): google resource ID for the drive folder to put the file into.
            filename (str): name of the uploaded file.
            file_stream (file-like/stream): contents of the file to upload.
            mimetype (str): mimetype of the given file.

        Returns: file ID (str).

        Throws:
            googleapiclient.errors.HttpError:
                For some non-retryable 4xx or 5xx error.  See the full list here:
                https://developers.google.com/drive/api/v3/handle-errors
        """
        file_metadata = {
            'name': filename,
            'parents': [folder_id],
        }
        media = MediaIoBaseUpload(file_stream, mimetype=mimetype)
        uploaded_file = self._client.files().create(  # pylint: disable=no-member
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        LOG.info('File uploaded: ID="{}", name="{}"'.format(uploaded_file.get('id'), filename))
        return uploaded_file.get('id')

    @backoff.on_exception(
        backoff.expo,
        HttpError,
        max_time=600,  # 10 minutes
        giveup=lambda e: not _should_retry_google_api(e),
        on_backoff=lambda details: _backoff_handler(details),  # pylint: disable=unnecessary-lambda
    )
    def delete_files(self, file_ids):
        """
        Delete multiple files forever, bypassing the "trash".

        This function takes advantage of request batching to reduce request volume.

        Args:
            file_ids (list of str): list of IDs for files to delete.
        """
        def callback(request_id, response, exception):  # pylint: disable=unused-argument,missing-docstring
            if exception:
                LOG.error(exception)
            else:
                LOG.info('Successfully deleted file.')

        batched_requests = self._client.new_batch_http_request(callback=callback)  # pylint: disable=no-member
        for file_id in file_ids:
            batched_requests.add(self._client.files().delete(fileId=file_id))  # pylint: disable=no-member
        batched_requests.execute()

    @backoff.on_exception(
        backoff.expo,
        HttpError,
        max_time=600,  # 10 minutes
        giveup=lambda e: not _should_retry_google_api(e),
        on_backoff=lambda details: _backoff_handler(details),  # pylint: disable=unnecessary-lambda
    )
    def list_subfolders(self, top_level, file_fields='id, name'):
        """
        List all subfolders of a given top level folder

        This function may make multiple HTTP requests depending on how many pages the response contains.  The default
        page size for the python google API client is 100 items.

        Args:
            top_level (str): ID of top level folder.
            file_fields (str): comma separated list of metadata fields to return for each folder. For a full list of
                file metadata fields, see https://developers.google.com/drive/api/v3/reference/files

        Returns: list of dicts, where each dict contains file metadata and each dict key corresponds to fields specified
            in the `file_fields` arg.

        Throws:
            googleapiclient.errors.HttpError:
                For some non-retryable 4xx or 5xx error.  See the full list here:
                https://developers.google.com/drive/api/v3/handle-errors
        """
        extra_kwargs = {}  # only used for carrying the pageToken.
        results = []
        while True:
            resp = self._client.files().list(  # pylint: disable=no-member
                q="mimeType = 'application/vnd.google-apps.folder' and '{}' in parents".format(top_level),
                fields='nextPageToken, files({})'.format(file_fields),
                **extra_kwargs
            ).execute()
            page_results = resp.get('files', [])
            results.extend(page_results)
            if page_results and 'nextPageToken' in resp and resp['nextPageToken']:
                # The presence of nextPageToken implies there are more pages, so another call is required to fetch the
                # next page.  Also, page_results must be nonempty since a provided nextPageToken coupled with empty page
                # list is wrong and we just interpret that as the last page.
                extra_kwargs['pageToken'] = resp['nextPageToken']
            else:
                break
        return results
