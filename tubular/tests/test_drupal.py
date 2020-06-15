"""
Tests of the code interacting with the Drupal API.
"""

import os
import shutil
import unittest
from mock import Mock, patch
from six.moves import reload_module

import tubular.drupal as drupal
from tubular.exception import BackendError

os.environ["TUBULAR_RETRY_ENABLED"] = "false"
reload_module(drupal)  # pylint: disable=too-many-function-args

ACQUIA_ENV = "test"
ACQUIA_ENV_ID = '123'
ACQUIA_APP_ID = '123-xyzd'

TEST_CLIENT_ID = 'client'
TEST_SECRET = 'secret'
TEST_TOKEN = 'test-token'
TEST_TAG = "tags/foo-bar"
TEST_NOTIFICATION_URL = "https://test-server/api/{}/notification/1234ffdd-0b22-4abcd-a949-1fd0fca61c6c".\
    format(ACQUIA_ENV_ID)
PATH_NAME = "../target/{env}_tag_name.txt"
DIR_NAME = PATH_NAME[:PATH_NAME.rfind("/")]


class TestDrupal(unittest.TestCase):
    """
    Class containing tests of all code interacting with Drupal.
    """
    @patch('tubular.drupal.get_acquia_v2')
    def test_check_state_waiting(self, mock_get_request):
        """
        Tests check_state raises BackendError because the status field is "In Progress"
        """

        mock_get_request.return_value = Mock()
        mock_get_request.return_value.status_code = 200
        mock_get_request.return_value.json.return_value = {'status': 'In Progress'}

        with self.assertRaises(BackendError):
            drupal.check_state(TEST_NOTIFICATION_URL, token=TEST_TOKEN)

    @patch('tubular.drupal.get_acquia_v2')
    def test_check_state_done(self, mock_get_request):
        """
        Tests check_state returns True because the status field is "completed"
        """
        mock_get_request.return_value = Mock()
        mock_get_request.return_value.status_code = 200
        mock_get_request.return_value.json.return_value = {'status': 'completed'}

        self.assertTrue(drupal.check_state(TEST_NOTIFICATION_URL, token=TEST_TOKEN))

    @patch('tubular.drupal.post_acquia_v2')
    @patch('tubular.drupal.get_api_token')
    @patch('tubular.drupal.fetch_environment_uid')
    def test_clear_varnish_cache_failure(self, mock_env_id, mock_token, mock_post_request):
        """
        Tests clear_varnish_cache raises BackendError when status != 200
        """

        mock_env_id.return_value = ACQUIA_ENV_ID
        mock_token.return_value = TEST_TOKEN
        mock_post_request.return_value = Mock()
        mock_post_request.return_value.status_code = 403

        with self.assertRaises(BackendError):
            drupal.clear_varnish_cache(app_id=ACQUIA_APP_ID, env=ACQUIA_ENV,
                                       client_id=TEST_CLIENT_ID, secret=TEST_SECRET)

    @patch('tubular.drupal.get_acquia_v2')
    @patch('tubular.drupal.post_acquia_v2')
    @patch('tubular.drupal.get_api_token')
    @patch('tubular.drupal.fetch_environment_uid')
    def test_clear_varnish_cache_success(self, mock_env_id, mock_token, mock_post_request, mock_get_request):
        """
        Tests clear_varnish_cache returns True when there is a valid response.
        """
        mock_env_id.return_value = ACQUIA_ENV_ID
        mock_token.return_value = TEST_TOKEN
        mock_post_request.return_value = Mock()
        mock_post_request.return_value.status_code = 202
        mock_post_request.return_value.json.return_value = {'_links': {'notification': {'href': TEST_NOTIFICATION_URL}}}
        mock_get_request.return_value = Mock()
        mock_get_request.return_value.status_code = 200
        mock_get_request.return_value.json.return_value = {'status': 'completed'}

        self.assertTrue(drupal.clear_varnish_cache(app_id=ACQUIA_APP_ID, env=ACQUIA_ENV,
                                                   client_id=TEST_CLIENT_ID, secret=TEST_SECRET))

    @patch('tubular.drupal.post_acquia_v2')
    @patch('tubular.drupal.get_api_token')
    @patch('tubular.drupal.fetch_environment_uid')
    def test_deploy_failure(self, mock_env_id, mock_token, mock_post_request):
        """
        Tests deploy raises BackendError when status != 200
        """

        mock_env_id.return_value = ACQUIA_ENV_ID
        mock_token.return_value = TEST_TOKEN
        mock_post_request.return_value = Mock()
        mock_post_request.return_value.status_code = 400

        with self.assertRaises(BackendError):
            drupal.deploy(app_id=ACQUIA_APP_ID, env=ACQUIA_ENV, client_id=TEST_CLIENT_ID, secret=TEST_SECRET,
                          branch_or_tag=TEST_TAG)

    @patch('tubular.drupal.get_acquia_v2')
    @patch('tubular.drupal.post_acquia_v2')
    @patch('tubular.drupal.get_api_token')
    @patch('tubular.drupal.fetch_environment_uid')
    def test_deploy_success(self, mock_env_id, mock_token, mock_post_request, mock_get_request):
        """
        Tests deploy returns True when there is a valid response.
        """
        mock_env_id.return_value = ACQUIA_ENV_ID
        mock_token.return_value = TEST_TOKEN
        mock_post_request.return_value = Mock()
        mock_post_request.return_value.status_code = 202
        mock_post_request.return_value.json.return_value = {'_links': {'notification': {'href': TEST_NOTIFICATION_URL}}}
        mock_get_request.return_value = Mock()
        mock_get_request.return_value.status_code = 200
        mock_get_request.return_value.json.return_value = {'status': 'completed'}

        self.assertTrue(drupal.deploy(app_id=ACQUIA_APP_ID, env=ACQUIA_ENV, client_id=TEST_CLIENT_ID,
                                      secret=TEST_SECRET, branch_or_tag=TEST_TAG))

    @patch('tubular.drupal.post_acquia_v2')
    @patch('tubular.drupal.get_api_token')
    @patch('tubular.drupal.fetch_environment_uid')
    def test_backup_database_failure(self, mock_env_id, mock_token, mock_post_request):
        """
        Tests backup_database raises BackendError when status != 200
        """
        mock_env_id.return_value = ACQUIA_ENV_ID
        mock_token.return_value = TEST_TOKEN
        mock_post_request.return_value = Mock()
        mock_post_request.return_value.status_code = 400

        with self.assertRaises(BackendError):
            drupal.backup_database(app_id=ACQUIA_APP_ID, env=ACQUIA_ENV, client_id=TEST_CLIENT_ID, secret=TEST_SECRET)

    @patch('tubular.drupal.get_acquia_v2')
    @patch('tubular.drupal.post_acquia_v2')
    @patch('tubular.drupal.get_api_token')
    @patch('tubular.drupal.fetch_environment_uid')
    def test_backup_database_success(self, mock_env_id, mock_token, mock_post_request, mock_get_request):
        """
        Tests backup_database returns True when there is a valid response.
        """
        mock_env_id.return_value = ACQUIA_ENV_ID
        mock_token.return_value = TEST_TOKEN
        mock_post_request.return_value = Mock()
        mock_post_request.return_value.status_code = 202
        mock_post_request.return_value.json.return_value = {'_links': {'notification': {'href': TEST_NOTIFICATION_URL}}}
        mock_get_request.return_value = Mock()
        mock_get_request.return_value.status_code = 200
        mock_get_request.return_value.json.return_value = {'status': 'completed'}

        self.assertTrue(drupal.backup_database(app_id=ACQUIA_APP_ID, env=ACQUIA_ENV,
                                               client_id=TEST_CLIENT_ID, secret=TEST_SECRET))

    @patch('tubular.drupal.get_acquia_v2')
    @patch('tubular.drupal.get_api_token')
    @patch('tubular.drupal.fetch_environment_uid')
    def test_fetch_deployed_tag_success(self, mock_env_id, mock_token, mock_get_request):
        """
        Tests fetch_deployed_tag returns the expected tag name.
        """
        mock_env_id.return_value = ACQUIA_ENV_ID
        mock_token.return_value = TEST_TOKEN
        mock_get_request.return_value = Mock()
        mock_get_request.return_value.status_code = 200

        mock_get_request.return_value.json.return_value = {
            'vcs': {
                'type': 'git',
                'path': TEST_TAG,
                'url': 'test@test.prod.hosting.acquia.com:test.git'
            }
        }
        os.makedirs(DIR_NAME)
        expected = TEST_TAG
        actual = drupal.fetch_deployed_tag(app_id=ACQUIA_APP_ID, env=ACQUIA_ENV, client_id=TEST_CLIENT_ID,
                                           secret=TEST_SECRET, path_name=PATH_NAME)
        shutil.rmtree(DIR_NAME)
        self.assertEqual(actual, expected)

    @patch('tubular.drupal.get_acquia_v2')
    @patch('tubular.drupal.get_api_token')
    @patch('tubular.drupal.fetch_environment_uid')
    def test_fetch_deployed_tag_failure(self, mock_env_id, mock_token, mock_get_request):
        """
        Tests fetch_deployed_tag raises BackendError when status != 200
        """
        mock_env_id.return_value = ACQUIA_ENV_ID
        mock_token.return_value = TEST_TOKEN
        mock_get_request.return_value = Mock()
        mock_get_request.return_value.status_code = 403

        with self.assertRaises(BackendError):
            drupal.fetch_deployed_tag(app_id=ACQUIA_APP_ID, env=ACQUIA_ENV, client_id=TEST_CLIENT_ID,
                                      secret=TEST_SECRET, path_name=PATH_NAME)

    def test_deploy_invalid_environment(self):
        """
        Tests KeyError is raised when an invalid environment is attempted.
        """
        with self.assertRaises(KeyError):
            drupal.deploy(app_id=ACQUIA_APP_ID, env='failure', client_id=TEST_CLIENT_ID,
                          secret=TEST_SECRET, branch_or_tag=TEST_TAG)
