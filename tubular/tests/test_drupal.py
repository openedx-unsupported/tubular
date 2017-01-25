"""
Tests of the code interacting with the Drupal API.
"""
from __future__ import unicode_literals

import os
import shutil
import unittest
import requests_mock
from six.moves import reload_module
import tubular.drupal as drupal
from tubular.exception import BackendError

os.environ["TUBULAR_RETRY_ENABLED"] = "false"
reload_module(drupal)  # pylint: disable=too-many-function-args

CLEAR_CACHE_RESPONSE_WAITING = {
    "id": "1",
    "queue": "purge-domain",
    "state": "waiting",
    "created": "1469543243",
    "started": None,
    "percentage": None,
    "completed": None,
    "sender": "test@edx.org",
    "recipient": None,
    "result": None,
    "hidden": "0",
    "cookie": None,
    "received": None,
    "tags": []
}

CLEAR_CACHE_RESPONSE_DONE = {
    "id": "1",
    "queue": "purge-domain",
    "state": "done",
    "description": "Clear web cache",
    "created": "1469481715",
    "started": "1469481715",
    "completed": "1469481716",
    "sender": "test@edx.org",
    "result": "",
    "cookie": None,
    "logs": "\n".join([
        "[21:21:55] [21:21:55] Started",
        "[21:21:56] [2016-07-25 21:21:56] Cleared domain cache",
    ])
}

DEPLOY_RESPONSE_WAITING = {
    "id": "2",
    "queue": "code-push",
    "state": "waiting",
    "description": "Deploy code to extra",
    "created": "1469542531",
    "started": None,
    "percentage": None,
    "completed": None,
    "sender": "test@edx.org",
    "recipient": None,
    "result": None,
    "hidden": "0",
    "cookie": None,
    "received": None,
    "tags": []
}

DEPLOY_RESPONSE_DONE = {
    "id": "2",
    "queue": "code-push",
    "state": "done",
    "description": "Deploy code to extra",
    "created": "1469542531",
    "started": "1469542531",
    "completed": "1469542534",
    "sender": "test@edx.org",
    "result": "",
    "cookie": None,
    "logs": "\n".join([
        "[14:15:31] [14:15:31] Started",
        "[14:15:34] [2016-07-26 14:15:32] updating web_servers[staging-8744].",
        "Updating to deploy tag",
        "Deploying tag on edx",
        "[2016-07-26 14:15:34] Starting hook: post-code-deploy",
        "[2016-07-26 14:15:34] Finished hook: post-code-deploy"
    ])
}

BACKUP_DATABASE_RESPONSE_WAITING = {
    "id": "3",
    "queue": "create-db-backup-ondemand",
    "state": "waiting",
    "description": "Backup database in extra.",
    "created": "1469721806",
    "started": None,
    "percentage": None,
    "completed": None,
    "sender": "test@edx.org",
    "recipient": None,
    "result": None,
    "hidden": "0",
    "cookie": None,
    "received": None,
    "tags": []
}

BACKUP_DATABASE_RESPONSE_STARTED = {
    "id": "3",
    "queue": "create-db-backup-ondemand",
    "state": "started",
    "description": "Backup database in extra.",
    "created": "1469721806",
    "started": "1469721807",
    "completed": None,
    "sender": "test@edx.org",
    "result": None,
    "cookie": None,
    "logs": "[16:03:27] [16:03:27] Started\n"
}

BACKUP_DATABASE_RESPONSE_DONE = {
    "id": "3",
    "queue": "create-db-backup-ondemand",
    "state": "done",
    "description": "Backup database in extra.",
    "created": "1469721806",
    "started": "1469721807",
    "completed": "1469721846",
    "sender": "test@edx.org",
    "result": '{\\"backupid\\":\\"33971734\\"}',
    "cookie": None,
    "logs": "\n".join(["[16:03:27] [16:03:27] Started", "[16:04:06] [16:04:06] Done"]),
}

FETCH_TAG_RESPONSE = {
    "name": "extra",
    "vcs_path": "tags/foo-bar",
    "ssh_host": "ssh.host",
    "db_clusters": ["1725"],
    "default_domain": "default.domain",
    "livedev": "disabled",
    "unix_username": "extra"
}

ACQUIA_ENV = "test"
ACQUIA_DOMAINS = [
    "edxstg.prod.acquia-sites.com",
    "stage-edx-mktg-backend.edx.org",
    "stage-edx-mktg-edit.edx.org",
    "stage-webview.edx.org",
    "stage.edx.org",
    "www.stage.edx.org",
]
TEST_USERNAME = "foo"
TEST_PASSWORD = "bar"
TEST_TAG = "tags/foo-bar"
PATH_NAME = "../target/{env}_tag_name.txt"
DIR_NAME = PATH_NAME[:PATH_NAME.rfind("/")]


@requests_mock.Mocker()
class TestDrupal(unittest.TestCase):
    """
    Class containing tests of all code interacting with Drupal.
    """
    def test_check_state_waiting(self, mock):
        """
        Tests check_state raises BackendError because the state field is "waiting"
        """
        mock.get(
            drupal.CHECK_TASKS_URL.format(id="1"),
            json=CLEAR_CACHE_RESPONSE_WAITING
        )
        with self.assertRaises(BackendError):
            drupal.check_state(task_id="1", username=TEST_USERNAME, password=TEST_PASSWORD)

    def test_check_state_done(self, mock):
        """
        Tests check_state returns True because the state field is "done"
        """
        mock.get(
            drupal.CHECK_TASKS_URL.format(id="1"),
            json=CLEAR_CACHE_RESPONSE_DONE
        )
        self.assertTrue(drupal.check_state(task_id="1", username=TEST_USERNAME, password=TEST_PASSWORD))

    def test_clear_varnish_cache_failure(self, mock):
        """
        Tests clear_varnish_cache raises BackendError when status != 200
        """
        for domain in ACQUIA_DOMAINS:
            mock.delete(
                drupal.CLEAR_CACHE_URL.format(env=ACQUIA_ENV, domain=domain),
                json={},
                status_code=401
            )
        with self.assertRaises(BackendError):
            drupal.clear_varnish_cache(env=ACQUIA_ENV, username=TEST_USERNAME, password=TEST_PASSWORD)

    def test_clear_varnish_cache_success(self, mock):
        """
        Tests clear_varnish_cache returns True when there is a valid response.
        """
        for domain in ACQUIA_DOMAINS:
            mock.delete(
                drupal.CLEAR_CACHE_URL.format(env=ACQUIA_ENV, domain=domain),
                json=CLEAR_CACHE_RESPONSE_WAITING,
            )
        mock.get(
            drupal.CHECK_TASKS_URL.format(id="1"),
            json=CLEAR_CACHE_RESPONSE_DONE
        )
        self.assertTrue(drupal.clear_varnish_cache(env=ACQUIA_ENV, username=TEST_USERNAME, password=TEST_PASSWORD))

    def test_deploy_failure(self, mock):
        """
        Tests deploy raises BackendError when status != 200
        """
        mock.post(
            drupal.DEPLOY_URL.format(env=ACQUIA_ENV, tag=TEST_TAG),
            json={},
            status_code=501
        )
        with self.assertRaises(BackendError):
            drupal.deploy(env=ACQUIA_ENV, username=TEST_USERNAME, password=TEST_PASSWORD, tag=TEST_TAG)

    def test_deploy_success(self, mock):
        """
        Tests deploy returns True when there is a valid response.
        """
        mock.post(
            drupal.DEPLOY_URL.format(env=ACQUIA_ENV, tag=TEST_TAG),
            json=DEPLOY_RESPONSE_WAITING,
        )
        mock.get(
            drupal.CHECK_TASKS_URL.format(id="2"),
            json=DEPLOY_RESPONSE_DONE
        )
        self.assertTrue(drupal.deploy(env=ACQUIA_ENV, username=TEST_USERNAME, password=TEST_PASSWORD, tag=TEST_TAG))

    def test_backup_database_failure(self, mock):
        """
        Tests backup_database raises BackendError when status != 200
        """
        mock.post(
            drupal.BACKUP_DATABASE_URL.format(env=ACQUIA_ENV),
            json={},
            status_code=501
        )
        with self.assertRaises(BackendError):
            drupal.backup_database(env=ACQUIA_ENV, username=TEST_USERNAME, password=TEST_PASSWORD)

    def test_backup_database_success(self, mock):
        """
        Tests backup_database returns True when there is a valid response.
        """
        mock.post(
            drupal.BACKUP_DATABASE_URL.format(env=ACQUIA_ENV),
            json=BACKUP_DATABASE_RESPONSE_WAITING,
        )
        mock.get(
            drupal.CHECK_TASKS_URL.format(id="3"),
            json=BACKUP_DATABASE_RESPONSE_STARTED
        )
        mock.get(
            drupal.CHECK_TASKS_URL.format(id="3"),
            json=BACKUP_DATABASE_RESPONSE_DONE
        )
        self.assertTrue(drupal.backup_database(env=ACQUIA_ENV, username=TEST_USERNAME, password=TEST_PASSWORD))

    def test_fetch_deployed_tag_success(self, mock):
        """
        Tests fetch_deployed_tag returns the expected tag name.
        """
        mock.get(
            drupal.FETCH_TAG_URL.format(env=ACQUIA_ENV),
            json=FETCH_TAG_RESPONSE
        )
        os.makedirs(DIR_NAME)
        expected = TEST_TAG
        actual = drupal.fetch_deployed_tag(env=ACQUIA_ENV, username=TEST_USERNAME,
                                           password=TEST_PASSWORD, path_name=PATH_NAME)
        shutil.rmtree(DIR_NAME)
        self.assertEqual(actual, expected)

    def test_fetch_deployed_tag_failure(self, mock):
        """
        Tests fetch_deployed_tag raises BackendError when status != 200
        """
        mock.get(
            drupal.FETCH_TAG_URL.format(env=ACQUIA_ENV),
            json={},
            status_code=403
        )
        with self.assertRaises(BackendError):
            drupal.fetch_deployed_tag(env=ACQUIA_ENV, username=TEST_USERNAME,
                                      password=TEST_PASSWORD, path_name=PATH_NAME)

    def test_deploy_invalid_environment(self, _mock):
        """
        Tests KeyError is raised when an invalid environment is attempted.
        """
        with self.assertRaises(KeyError):
            drupal.deploy(env="failure", username=TEST_USERNAME, password=TEST_PASSWORD, tag=TEST_TAG)
