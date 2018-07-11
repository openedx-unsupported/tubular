"""
Common functionality for retirement related tests
"""
import json
import yaml


TEST_RETIREMENT_PIPELINE = [
    ['RETIRING_FORUMS', 'FORUMS_COMPLETE', 'LMS', 'retirement_retire_forum'],
    ['RETIRING_EMAIL_LISTS', 'EMAIL_LISTS_COMPLETE', 'LMS', 'retirement_retire_mailings'],
    ['RETIRING_ENROLLMENTS', 'ENROLLMENTS_COMPLETE', 'LMS', 'retirement_unenroll'],
    ['RETIRING_LMS', 'LMS_COMPLETE', 'LMS', 'retirement_lms_retire']
]

TEST_RETIREMENT_END_STATES = [state[1] for state in TEST_RETIREMENT_PIPELINE]
TEST_RETIREMENT_QUEUE_STATES = ['PENDING'] + TEST_RETIREMENT_END_STATES


def fake_config_file(f, orgs=None, partner_folder_mapping=None, drive_partners_folder=None):
    """
    Create a config file for a single test. Combined with CliRunner.isolated_filesystem() to
    ensure the file lifetime is limited to the test. See _call_script for usage.
    """

    if orgs is None:
        orgs = {
            'org1': 'Org1X',
            'org2': 'Org2X',
            'org3': 'Org3X',
        }

    if partner_folder_mapping is None:
        partner_folder_mapping = {
            'Org1X': 'Org1X_folder',
            'Org2X': 'Org2X_folder',
            'Org3X': 'Org3X_folder',
        }

    if drive_partners_folder is None:
        drive_partners_folder = 'FakeDriveID'

    config = {
        'client_id': 'bogus id',
        'client_secret': 'supersecret',
        'base_urls': {
            'credentials': 'https://credentials.stage.edx.org/',
            'lms': 'https://stage-edx-edxapp.edx.org/',
            'ecommerce': 'https://ecommerce.stage.edx.org/'
        },
        'retirement_pipeline': TEST_RETIREMENT_PIPELINE,
        'org_partner_mapping': orgs,
        'partner_folder_mapping': partner_folder_mapping,
        'drive_partners_folder': drive_partners_folder
    }

    yaml.safe_dump(config, f)


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
