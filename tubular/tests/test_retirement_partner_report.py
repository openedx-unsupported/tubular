# coding=utf-8
"""
Test the retire_one_learner.py script
"""
from __future__ import print_function

import csv
import os
import unicodedata
from datetime import date
import time

from click.testing import CliRunner
from mock import ANY, DEFAULT, patch
from six import PY2

from tubular.scripts.retirement_partner_report import (
    ERR_BAD_CONFIG,
    ERR_BAD_SECRETS,
    ERR_CLEANUP,
    ERR_FETCHING_LEARNERS,
    ERR_NO_CONFIG,
    ERR_NO_SECRETS,
    ERR_NO_OUTPUT_DIR,
    ERR_REPORTING,
    ERR_SETUP_FAILED,
    ERR_UNKNOWN_ORG,
    REPORTING_FILENAME_PREFIX,
    generate_report
)
from tubular.tests.retirement_helpers import fake_config_file, fake_google_secrets_file, FAKE_ORGS, TEST_PLATFORM_NAME


TEST_CONFIG_YML_NAME = 'test_config.yml'
TEST_GOOGLE_SECRETS_FILENAME = 'test_google_secrets.json'
DELETION_TIME = time.strftime("%Y-%m-%dT%H:%M:%S")
UNICODE_NAME_CONSTANT = '阿碧'
USER_ID = '12345'


def _call_script(expect_success=True, config_orgs=None):
    """
    Call the retired learner script with the given username and a generic, temporary config file.
    Returns the CliRunner.invoke results
    """
    if config_orgs is None:
        config_orgs = FAKE_ORGS

    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_YML_NAME, 'w') as config_f:
            fake_config_file(config_f, config_orgs)
        with open(TEST_GOOGLE_SECRETS_FILENAME, 'w') as secrets_f:
            fake_google_secrets_file(secrets_f)

        tmp_output_dir = 'test_output_dir'
        os.mkdir(tmp_output_dir)

        result = runner.invoke(
            generate_report,
            args=[
                '--config_file',
                TEST_CONFIG_YML_NAME,
                '--google_secrets_file',
                TEST_GOOGLE_SECRETS_FILENAME,
                '--output_dir',
                tmp_output_dir
            ]
        )

        print(result)
        print(result.output)

        if expect_success:
            assert result.exit_code == 0

            if config_orgs is None:
                # These are the orgs
                config_org_vals = FAKE_ORGS.values()
            else:
                config_org_vals = config_orgs.values()

            # Normalize the unicode as the script does
            if PY2:
                config_org_vals = [org.decode('utf-8') for org in config_org_vals]

            config_org_vals = [unicodedata.normalize('NFKC', org) for org in config_org_vals]

            for org in config_org_vals:
                outfile = os.path.join(tmp_output_dir, '{}_{}_{}_{}.csv'.format(
                    REPORTING_FILENAME_PREFIX, TEST_PLATFORM_NAME, org, date.today().isoformat()
                ))

                with open(outfile, 'r') as csvfile:
                    reader = csv.DictReader(csvfile)
                    rows = []
                    for row in reader:
                        # Check the user_id value is in the correct place
                        assert USER_ID in row['user_id']

                        # Check username value is in the correct place
                        assert 'username' in row['original_username']

                        # Check email value is in the correct place
                        assert 'invalid' in row['original_email']

                        # Check name value is in the correct place
                        assert UNICODE_NAME_CONSTANT in row['original_name']

                        # Check deletion_completed value is in the correct place
                        assert DELETION_TIME in row['deletion_completed']

                        rows.append(row)

                # Confirm that there are rows at all
                assert len(rows)
    return result


def _fake_retirement_report_user(seed_val, user_orgs=None):
    """
    Creates unique user to populate a fake report with.
    - seed_val is a number or other unique value for this user, will be formatted into
      user values to make sure they're distinct.
    - user_orgs, if given, should be a list of orgs that will be associated with the user.
    """
    if user_orgs is None:
        user_orgs = list(FAKE_ORGS.keys())

    return {
        'user_id': USER_ID,
        'original_username': 'username_{}'.format(seed_val),
        'original_email': 'user_{}@foo.invalid'.format(seed_val),
        'original_name': '{} {}'.format(UNICODE_NAME_CONSTANT, seed_val),
        'orgs': user_orgs,
        'created': DELETION_TIME,
    }


def _fake_retirement_report(num_users=10):
    """
    Fake the output of a retirement report with unique users
    """
    return [_fake_retirement_report_user(i) for i in range(num_users)]


@patch('tubular.google_api.DriveApi.__init__')
@patch('tubular.google_api.DriveApi.create_file_in_folder')
@patch('tubular.google_api.DriveApi.walk_files')
@patch('tubular.google_api.DriveApi.create_comments_for_files')
@patch('tubular.edx_api.BaseApiClient.get_access_token')
@patch.multiple(
    'tubular.edx_api.LmsApi',
    retirement_partner_report=DEFAULT,
    retirement_partner_cleanup=DEFAULT
)
def test_successful_report(*args, **kwargs):
    mock_get_access_token = args[0]
    mock_create_comments = args[1]
    mock_walk_files = args[2]
    mock_create_files = args[3]
    mock_driveapi = args[4]
    mock_retirement_report = kwargs['retirement_partner_report']
    mock_retirement_cleanup = kwargs['retirement_partner_cleanup']

    mock_get_access_token.return_value = ('THIS_IS_A_JWT', None)
    mock_create_comments.return_value = None
    mock_walk_files.return_value = [{'name': partner, 'id': 'folder' + partner} for partner in FAKE_ORGS.values()]
    mock_create_files.side_effect = ['foo', 'bar', 'baz']
    mock_driveapi.return_value = None
    mock_retirement_report.return_value = _fake_retirement_report()

    result = _call_script()

    # Make sure we're getting the LMS token
    mock_get_access_token.assert_called_once()

    # Make sure that we get the report
    mock_retirement_report.assert_called_once()

    # Make sure we tried to upload the files
    assert mock_create_files.call_count == 3

    # Make sure we tried to add comments to the files
    assert mock_create_comments.call_count == 1
    mock_create_comments.assert_called_with(['foo', 'bar', 'baz'], ANY)

    # Make sure we tried to remove the users from the queue
    mock_retirement_cleanup.assert_called_with(
        [{'original_username': user['original_username']} for user in mock_retirement_report.return_value]
    )

    assert 'All reports completed and uploaded to Google.' in result.output


def test_no_config():
    runner = CliRunner()
    result = runner.invoke(generate_report)
    print(result.output)
    assert result.exit_code == ERR_NO_CONFIG
    assert 'No config file' in result.output


def test_no_secrets():
    runner = CliRunner()
    result = runner.invoke(generate_report, args=['--config_file', 'does_not_exist.yml'])
    print(result.output)
    assert result.exit_code == ERR_NO_SECRETS
    assert 'No secrets file' in result.output


def test_no_output_dir():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_YML_NAME, 'w') as config_f:
            config_f.write('irrelevant')

        with open(TEST_GOOGLE_SECRETS_FILENAME, 'w') as config_f:
            config_f.write('irrelevant')

        result = runner.invoke(
            generate_report,
            args=[
                '--config_file',
                TEST_CONFIG_YML_NAME,
                '--google_secrets_file',
                TEST_GOOGLE_SECRETS_FILENAME
            ]
        )
    print(result.output)
    assert result.exit_code == ERR_NO_OUTPUT_DIR
    assert 'No output_dir' in result.output


def test_bad_config():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_YML_NAME, 'w') as config_f:
            config_f.write(']this is bad yaml')

        with open(TEST_GOOGLE_SECRETS_FILENAME, 'w') as config_f:
            config_f.write('{this is bad json but we should not get to parsing it')

        tmp_output_dir = 'test_output_dir'
        os.mkdir(tmp_output_dir)

        result = runner.invoke(
            generate_report,
            args=[
                '--config_file',
                TEST_CONFIG_YML_NAME,
                '--google_secrets_file',
                TEST_GOOGLE_SECRETS_FILENAME,
                '--output_dir',
                tmp_output_dir
            ]
        )
        print(result.output)
        assert result.exit_code == ERR_BAD_CONFIG
        assert 'Failed to read' in result.output


def test_bad_secrets():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_YML_NAME, 'w') as config_f:
            fake_config_file(config_f)

        with open(TEST_GOOGLE_SECRETS_FILENAME, 'w') as config_f:
            config_f.write('{this is bad json')

        tmp_output_dir = 'test_output_dir'
        os.mkdir(tmp_output_dir)

        result = runner.invoke(
            generate_report,
            args=[
                '--config_file',
                TEST_CONFIG_YML_NAME,
                '--google_secrets_file',
                TEST_GOOGLE_SECRETS_FILENAME,
                '--output_dir',
                tmp_output_dir
            ]
        )
        print(result.output)
        assert result.exit_code == ERR_BAD_SECRETS
        assert 'Failed to read' in result.output


def test_bad_output_dir():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_YML_NAME, 'w') as config_f:
            fake_config_file(config_f)

        with open(TEST_GOOGLE_SECRETS_FILENAME, 'w') as config_f:
            fake_google_secrets_file(config_f)

        result = runner.invoke(
            generate_report,
            args=[
                '--config_file',
                TEST_CONFIG_YML_NAME,
                '--google_secrets_file',
                TEST_GOOGLE_SECRETS_FILENAME,
                '--output_dir',
                'does_not_exist/at_all'
            ]
        )
        print(result.output)
        assert result.exit_code == ERR_NO_OUTPUT_DIR
        assert 'or path does not exist' in result.output


@patch('tubular.edx_api.BaseApiClient.get_access_token')
def test_setup_failed(*args):
    mock_get_access_token = args[0]
    mock_get_access_token.side_effect = Exception('boom')

    result = _call_script(expect_success=False)
    mock_get_access_token.assert_called_once()
    assert result.exit_code == ERR_SETUP_FAILED


@patch('tubular.google_api.DriveApi.__init__')
@patch('tubular.google_api.DriveApi.walk_files')
@patch('tubular.edx_api.BaseApiClient.get_access_token')
@patch.multiple(
    'tubular.edx_api.LmsApi',
    retirement_partner_report=DEFAULT)
def test_fetching_learners_failed(*args, **kwargs):
    mock_get_access_token = args[0]
    mock_walk_files = args[1]
    mock_drive_init = args[2]
    mock_retirement_report = kwargs['retirement_partner_report']

    mock_get_access_token.return_value = ('THIS_IS_A_JWT', None)
    mock_walk_files.return_value = []
    mock_drive_init.return_value = None
    mock_retirement_report.side_effect = Exception('failed to get learners')

    result = _call_script(expect_success=False)

    assert result.exit_code == ERR_FETCHING_LEARNERS
    assert 'failed to get learners' in result.output


@patch('tubular.google_api.DriveApi.__init__')
@patch('tubular.google_api.DriveApi.walk_files')
@patch('tubular.edx_api.BaseApiClient.get_access_token')
@patch.multiple(
    'tubular.edx_api.LmsApi',
    retirement_partner_report=DEFAULT)
def test_unknown_org(*args, **kwargs):
    mock_get_access_token = args[0]
    mock_drive_init = args[2]
    mock_retirement_report = kwargs['retirement_partner_report']

    mock_drive_init.return_value = None
    mock_get_access_token.return_value = ('THIS_IS_A_JWT', None)

    orgs = ['orgA', 'orgB']

    mock_retirement_report.return_value = [_fake_retirement_report_user(i, orgs) for i in range(10)]

    result = _call_script(expect_success=False)

    assert result.exit_code == ERR_UNKNOWN_ORG
    assert 'orgA' in result.output


@patch('tubular.google_api.DriveApi.__init__')
@patch('tubular.google_api.DriveApi.walk_files')
@patch('tubular.edx_api.BaseApiClient.get_access_token')
@patch('csv.DictWriter')
@patch('tubular.edx_api.LmsApi.retirement_partner_report')
def test_reporting_error(*args):
    mock_retirement_report = args[0]
    mock_dictwriter = args[1]
    mock_get_access_token = args[2]
    mock_drive_init = args[4]

    error_msg = 'Fake unable to write csv'

    mock_get_access_token.return_value = ('THIS_IS_A_JWT', None)
    mock_dictwriter.side_effect = Exception(error_msg)
    mock_drive_init.return_value = None
    mock_retirement_report.return_value = _fake_retirement_report()

    result = _call_script(expect_success=False)

    assert result.exit_code == ERR_REPORTING
    assert error_msg in result.output


@patch('tubular.google_api.DriveApi.walk_files')
@patch('tubular.google_api.DriveApi.__init__')
@patch('tubular.google_api.DriveApi.create_file_in_folder')
@patch('tubular.edx_api.BaseApiClient.get_access_token')
@patch.multiple(
    'tubular.edx_api.LmsApi',
    retirement_partner_report=DEFAULT,
    retirement_partner_cleanup=DEFAULT
)
def test_cleanup_error(*args, **kwargs):
    mock_get_access_token = args[0]
    mock_create_files = args[1]
    mock_driveapi = args[2]
    mock_walk_files = args[3]
    mock_retirement_report = kwargs['retirement_partner_report']
    mock_retirement_cleanup = kwargs['retirement_partner_cleanup']

    mock_get_access_token.return_value = ('THIS_IS_A_JWT', None)
    mock_create_files.return_value = True
    mock_driveapi.return_value = None
    mock_walk_files.return_value = [{'name': partner, 'id': 'folder' + partner} for partner in FAKE_ORGS.values()]

    mock_retirement_report.return_value = _fake_retirement_report()
    mock_retirement_cleanup.side_effect = Exception('Mock cleanup exception')

    result = _call_script(expect_success=False)

    assert mock_retirement_cleanup.called_with(
        [user['original_username'] for user in mock_retirement_report.return_value]
    )

    assert result.exit_code == ERR_CLEANUP
    assert 'Users may be stuck in the processing state!' in result.output


@patch('tubular.google_api.DriveApi.__init__')
@patch('tubular.google_api.DriveApi.create_file_in_folder')
@patch('tubular.google_api.DriveApi.walk_files')
@patch('tubular.google_api.DriveApi.create_comments_for_files')
@patch('tubular.edx_api.BaseApiClient.get_access_token')
@patch.multiple(
    'tubular.edx_api.LmsApi',
    retirement_partner_report=DEFAULT,
    retirement_partner_cleanup=DEFAULT
)
def test_google_unicode_folder_names(*args, **kwargs):
    mock_get_access_token = args[0]
    mock_create_comments = args[1]
    mock_walk_files = args[2]
    mock_create_files = args[3]
    mock_driveapi = args[4]
    mock_retirement_report = kwargs['retirement_partner_report']
    mock_retirement_cleanup = kwargs['retirement_partner_cleanup']

    mock_get_access_token.return_value = ('THIS_IS_A_JWT', None)
    mock_walk_files.return_value = [
        {'name': unicodedata.normalize('NFKC', u'TéstX'), 'id': 'org1'},
        {'name': unicodedata.normalize('NFKC', u'TéstX2'), 'id': 'org2'},
        {'name': unicodedata.normalize('NFKC', u'TéstX3'), 'id': 'org3'},
    ]
    mock_create_files.side_effect = ['foo', 'bar', 'baz']
    mock_driveapi.return_value = None
    mock_retirement_report.return_value = _fake_retirement_report()

    config_orgs = {
        'org1': unicodedata.normalize('NFKC', u'TéstX'),
        'org2': unicodedata.normalize('NFD', u'TéstX2'),
        'org3': unicodedata.normalize('NFKD', u'TéstX3'),
    }

    result = _call_script(config_orgs=config_orgs)

    # Make sure we're getting the LMS token
    mock_get_access_token.assert_called_once()

    # Make sure that we get the report
    mock_retirement_report.assert_called_once()

    # Make sure we tried to upload the files
    assert mock_create_files.call_count == 3

    # Make sure we tried to add comments to the files
    assert mock_create_comments.call_count == 1
    mock_create_comments.assert_called_with(['foo', 'bar', 'baz'], ANY)

    # Make sure we tried to remove the users from the queue
    mock_retirement_cleanup.assert_called_with(
        [{'original_username': user['original_username']} for user in mock_retirement_report.return_value]
    )

    assert 'All reports completed and uploaded to Google.' in result.output
