# coding=utf-8

"""
Common functionality for retirement related tests
"""
import json
import unicodedata

import yaml


TEST_RETIREMENT_PIPELINE = [
    ['RETIRING_FORUMS', 'FORUMS_COMPLETE', 'LMS', 'retirement_retire_forum'],
    ['RETIRING_EMAIL_LISTS', 'EMAIL_LISTS_COMPLETE', 'LMS', 'retirement_retire_mailings'],
    ['RETIRING_ENROLLMENTS', 'ENROLLMENTS_COMPLETE', 'LMS', 'retirement_unenroll'],
    ['RETIRING_LMS', 'LMS_COMPLETE', 'LMS', 'retirement_lms_retire']
]

TEST_RETIREMENT_END_STATES = [state[1] for state in TEST_RETIREMENT_PIPELINE]
TEST_RETIREMENT_QUEUE_STATES = ['PENDING'] + TEST_RETIREMENT_END_STATES

FAKE_ORGS = {
    # Make sure unicode names, as they should come in from the yaml config, work
    'org1': unicodedata.normalize('NFKC', u'TéstX'),
    'org2': 'Org2X',
    'org3': 'Org3X',
}

TEST_PLATFORM_NAME = 'fakename'

TEST_DENIED_NOTIFICATION_DOMAINS = {
    '@edx.org',
    '@partner-reporting-automation.iam.gserviceaccount.com',
}


def fake_config_file(f, orgs=None, fetch_ecom_segment_id=False):
    """
    Create a config file for a single test. Combined with CliRunner.isolated_filesystem() to
    ensure the file lifetime is limited to the test. See _call_script for usage.
    """
    if orgs is None:
        orgs = FAKE_ORGS

    config = {
        'client_id': 'bogus id',
        'client_secret': 'supersecret',
        'base_urls': {
            'credentials': 'https://credentials.stage.edx.invalid/',
            'lms': 'https://stage-edx-edxapp.edx.invalid/',
            'ecommerce': 'https://ecommerce.stage.edx.invalid/',
            'segment': 'https://segment.invalid/graphql',
        },
        'retirement_pipeline': TEST_RETIREMENT_PIPELINE,
        'partner_report_platform_name': TEST_PLATFORM_NAME,
        'org_partner_mapping': orgs,
        'drive_partners_folder': 'FakeDriveID',
        'denied_notification_domains': TEST_DENIED_NOTIFICATION_DOMAINS,
        'sailthru_key': 'fake_sailthru_key',
        'sailthru_secret': 'fake_sailthru_secret',
        's3_archive': {
            'bucket_name': 'fake_test_bucket',
            'region': 'fake_region',
        },
        'segment_workspace_slug': 'test_slug',
        'segment_auth_token': 'fakeauthtoken',
    }

    if fetch_ecom_segment_id:
        config['fetch_ecommerce_segment_id'] = True

    yaml.safe_dump(config, f)


def get_fake_user_retirement(
        retirement_id=1,
        original_username="foo_username",
        original_email="foo@edx.invalid",
        original_name="Foo User",
        retired_username="retired_user__asdf123",
        retired_email="retired_user__asdf123",
        ecommerce_segment_id="ecommerce-90",
        user_id=9009,
        current_username="foo_username",
        current_email="foo@edx.invalid",
        current_name="Foo User",
        current_state_name="PENDING",
        last_state_name="PENDING",
):
    """
    Return a "learner" used in retirment in the serialized format we get from LMS.
    """
    return {
        "id": retirement_id,
        "current_state": {
            "id": 1,
            "state_name": current_state_name,
            "state_execution_order": 10,
        },
        "last_state": {
            "id": 1,
            "state_name": last_state_name,
            "state_execution_order": 10,
        },
        "original_username": original_username,
        "original_email": original_email,
        "original_name": original_name,
        "retired_username": retired_username,
        "retired_email": retired_email,
        "ecommerce_segment_id": ecommerce_segment_id,
        "user": {
            "id": user_id,
            "username": current_username,
            "email": current_email,
            "profile": {
                "id": 10009,
                "name": current_name
            }
        },
        "created": "2018-10-18T20:08:03.724805",
        "modified": "2018-10-18T20:08:03.724805",
    }


def fake_google_secrets_file(f):
    """
    Create a fake google secrets file for a single test.
    """
    fake_private_key = """
-----BEGIN PRIVATE KEY-----
-----END PRIVATE KEY-----
    r"""

    secrets = {
        "type": "service_account",
        "project_id": "partner-reporting-automation",
        "private_key_id": "foo",
        "private_key": fake_private_key,
        "client_email": "bogus@serviceacct.invalid",
        "client_id": "411",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://accounts.google.com/o/oauth2/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/foo"
    }

    json.dump(secrets, f)
