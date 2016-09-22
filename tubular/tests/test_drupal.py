"""
Tests of the code interacting with the Drupal API.
"""
from __future__ import unicode_literals

import os
import shutil
import unittest
import httpretty
import tubular.drupal as drupal
from tubular.exception import BackendError

os.environ["TUBULAR_RETRY_ENABLED"] = "false"
reload(drupal)

CLEAR_CACHE_RESPONSE_WAITING = """
{
"id":"1",
"queue":"purge-domain",
"state":"waiting",
"created":"1469543243",
"started":null,
"percentage":null,
"completed":null,
"sender":"test@edx.org",
"recipient":null,
"result":null,
"hidden":"0",
"cookie":null,
"received":null,
"tags":[]
}
"""

CLEAR_CACHE_RESPONSE_DONE = """
{
"id":"1",
"queue":"purge-domain",
"state":"done",
"description":"Clear web cache",
"created":"1469481715",
"started":"1469481715",
"completed":"1469481716",
"sender":"test@edx.org",
"result":"",
"cookie":null,
"logs":"[21:21:55] [21:21:55] Started\\n[21:21:56] [2016-07-25 21:21:56] Cleared domain cache\\n"
}
"""

DEPLOY_RESPONSE_WAITING = """
{
"id":"2",
"queue":"code-push",
"state":"waiting",
"description":"Deploy code to extra",
"created":"1469542531",
"started":null,
"percentage":null,
"completed":null,
"sender":"test@edx.org",
"recipient":null,
"result":null,
"hidden":"0",
"cookie":null,
"received":null,
"tags":[]
}
"""

DEPLOY_RESPONSE_DONE = """
{
"id":"2",
"queue":"code-push",
"state":"done",
"description":"Deploy code to extra",
"created":"1469542531",
"started":"1469542531",
"completed":"1469542534",
"sender":"test@edx.org",
"result":"",
"cookie":null,
"logs":"[14:15:31] [14:15:31] Started\\n[14:15:34] [2016-07-26 14:15:32] updating web_servers[staging-8744].\\nUpdating to deploy tag\\nDeploying tag on edx\\n[2016-07-26 14:15:34] Starting hook: post-code-deploy\\n[2016-07-26 14:15:34] Finished hook: post-code-deploy\\n"
}
"""

BACKUP_DATABASE_RESPONSE_WAITING = """
{
"id":"3",
"queue":"create-db-backup-ondemand",
"state":"waiting",
"description":"Backup database in extra.",
"created":"1469721806",
"started":null,
"percentage":null,
"completed":null,
"sender":"test@edx.org",
"recipient":null,
"result":null,
"hidden":"0",
"cookie":null,
"received":null,
"tags":[]
}
"""

BACKUP_DATABASE_RESPONSE_STARTED = """
{
"id":"3",
"queue":"create-db-backup-ondemand",
"state":"started",
"description":"Backup database in extra.",
"created":"1469721806",
"started":"1469721807",
"completed":null,
"sender":"test@edx.org",
"result":null,
"cookie":null,
"logs":"[16:03:27] [16:03:27] Started\\n"
}
"""

BACKUP_DATABASE_RESPONSE_DONE = """
{
"id":"3",
"queue":"create-db-backup-ondemand",
"state":"done",
"description":"Backup database in extra.",
"created":"1469721806",
"started":"1469721807",
"completed":"1469721846",
"sender":"test@edx.org",
"result":"{\\"backupid\\":\\"33971734\\"}",
"cookie":null,
"logs":"[16:03:27] [16:03:27] Started\\n[16:04:06] [16:04:06] Done\\n"
}
"""

FETCH_TAG_RESPONSE = """
{
"name":"extra",
"vcs_path":"tags/foo-bar",
"ssh_host":"ssh.host",
"db_clusters":["1725"],
"default_domain":"default.domain",
"livedev":"disabled",
"unix_username":"extra"
}
"""

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


class TestDrupal(unittest.TestCase):
    """
    Class containing tests of all code interacting with Drupal.
    """
    @httpretty.activate
    def test_check_state_waiting(self):
        """
        Tests check_state raises BackendError because the state field is "waiting"
        """
        httpretty.register_uri(
            httpretty.GET,
            drupal.CHECK_TASKS_URL.format(id="1"),
            body=CLEAR_CACHE_RESPONSE_WAITING,
            content_type="application/json"
        )
        with self.assertRaises(BackendError):
            drupal.check_state(task_id="1", username=TEST_USERNAME, password=TEST_PASSWORD)

    @httpretty.activate
    def test_check_state_done(self):
        """
        Tests check_state returns True because the state field is "done"
        """
        httpretty.register_uri(
            httpretty.GET,
            drupal.CHECK_TASKS_URL.format(id="1"),
            body=CLEAR_CACHE_RESPONSE_DONE,
            content_type="application/json"
        )
        self.assertTrue(drupal.check_state(task_id="1", username=TEST_USERNAME, password=TEST_PASSWORD))

    @httpretty.activate
    def test_clear_varnish_cache_failure(self):
        """
        Tests clear_varnish_cache raises BackendError when status != 200
        """
        for domain in ACQUIA_DOMAINS:
            httpretty.register_uri(
                httpretty.DELETE,
                drupal.CLEAR_CACHE_URL.format(env=ACQUIA_ENV, domain=domain),
                body="{}",
                content_type="application/json",
                status=401
            )
        with self.assertRaises(BackendError):
            drupal.clear_varnish_cache(env=ACQUIA_ENV, username=TEST_USERNAME, password=TEST_PASSWORD)

    @httpretty.activate
    def test_clear_varnish_cache_success(self):
        """
        Tests clear_varnish_cache returns True when there is a valid response.
        """
        for domain in ACQUIA_DOMAINS:
            httpretty.register_uri(
                httpretty.DELETE,
                drupal.CLEAR_CACHE_URL.format(env=ACQUIA_ENV, domain=domain),
                body=CLEAR_CACHE_RESPONSE_WAITING,
                content_type="application/json"
            )
        httpretty.register_uri(
            httpretty.GET,
            drupal.CHECK_TASKS_URL.format(id="1"),
            body=CLEAR_CACHE_RESPONSE_DONE,
            content_type="application/json"
        )
        self.assertTrue(drupal.clear_varnish_cache(env=ACQUIA_ENV, username=TEST_USERNAME, password=TEST_PASSWORD))

    @httpretty.activate
    def test_deploy_failure(self):
        """
        Tests deploy raises BackendError when status != 200
        """
        httpretty.register_uri(
            httpretty.POST,
            drupal.DEPLOY_URL.format(env=ACQUIA_ENV, tag=TEST_TAG),
            body="{}",
            content_type="application/json",
            status=501
        )
        with self.assertRaises(BackendError):
            drupal.deploy(env=ACQUIA_ENV, username=TEST_USERNAME, password=TEST_PASSWORD, tag=TEST_TAG)

    @httpretty.activate
    def test_deploy_success(self):
        """
        Tests deploy returns True when there is a valid response.
        """
        httpretty.register_uri(
            httpretty.POST,
            drupal.DEPLOY_URL.format(env=ACQUIA_ENV, tag=TEST_TAG),
            body=DEPLOY_RESPONSE_WAITING,
            content_type="application/json",
        )
        httpretty.register_uri(
            httpretty.GET,
            drupal.CHECK_TASKS_URL.format(id="2"),
            body=DEPLOY_RESPONSE_DONE,
            content_type="application/json"
        )
        self.assertTrue(drupal.deploy(env=ACQUIA_ENV, username=TEST_USERNAME, password=TEST_PASSWORD, tag=TEST_TAG))

    @httpretty.activate
    def test_backup_database_failure(self):
        """
        Tests backup_database raises BackendError when status != 200
        """
        httpretty.register_uri(
            httpretty.POST,
            drupal.BACKUP_DATABASE_URL.format(env=ACQUIA_ENV),
            body="{}",
            content_type="application/json",
            status=501
        )
        with self.assertRaises(BackendError):
            drupal.backup_database(env=ACQUIA_ENV, username=TEST_USERNAME, password=TEST_PASSWORD)

    @httpretty.activate
    def test_backup_database_success(self):
        """
        Tests backup_database returns True when there is a valid response.
        """
        httpretty.register_uri(
            httpretty.POST,
            drupal.BACKUP_DATABASE_URL.format(env=ACQUIA_ENV),
            body=BACKUP_DATABASE_RESPONSE_WAITING,
            content_type="application/json",
        )
        httpretty.register_uri(
            httpretty.GET,
            drupal.CHECK_TASKS_URL.format(id="3"),
            body=BACKUP_DATABASE_RESPONSE_STARTED,
            content_type="application/json"
        )
        httpretty.register_uri(
            httpretty.GET,
            drupal.CHECK_TASKS_URL.format(id="3"),
            body=BACKUP_DATABASE_RESPONSE_DONE,
            content_type="application/json"
        )
        self.assertTrue(drupal.backup_database(env=ACQUIA_ENV, username=TEST_USERNAME, password=TEST_PASSWORD))

    @httpretty.activate
    def test_fetch_deployed_tag_success(self):
        """
        Tests fetch_deployed_tag returns the expected tag name.
        """
        httpretty.register_uri(
            httpretty.GET,
            drupal.FETCH_TAG_URL.format(env=ACQUIA_ENV),
            body=FETCH_TAG_RESPONSE,
            content_type="application/json"
        )
        os.makedirs(DIR_NAME)
        expected = TEST_TAG
        actual = drupal.fetch_deployed_tag(env=ACQUIA_ENV, username=TEST_USERNAME,
                                           password=TEST_PASSWORD, path_name=PATH_NAME)
        shutil.rmtree(DIR_NAME)
        self.assertEqual(actual, expected)

    @httpretty.activate
    def test_fetch_deployed_tag_failure(self):
        """
        Tests fetch_deployed_tag raises BackendError when status != 200
        """
        httpretty.register_uri(
            httpretty.GET,
            drupal.FETCH_TAG_URL.format(env=ACQUIA_ENV),
            body="{}",
            content_type="application/json",
            status=403
        )
        with self.assertRaises(BackendError):
            drupal.fetch_deployed_tag(env=ACQUIA_ENV, username=TEST_USERNAME,
                                      password=TEST_PASSWORD, path_name=PATH_NAME)

    def test_deploy_invalid_environment(self):
        """
        Tests KeyError is raised when an invalid environment is attempted.
        """
        with self.assertRaises(KeyError):
            drupal.deploy(env="failure", username=TEST_USERNAME, password=TEST_PASSWORD, tag=TEST_TAG)
