# coding=utf-8
"""
Test the retire_one_learner.py script
"""


import os

from click.testing import CliRunner
from mock import patch

from tubular.scripts.delete_expired_partner_gdpr_reports import (
    ERR_NO_CONFIG,
    ERR_BAD_CONFIG,
    ERR_NO_SECRETS,
    ERR_BAD_SECRETS,
    ERR_DELETING_REPORTS,
    ERR_BAD_AGE,
    delete_expired_reports
)
from tubular.scripts.retirement_partner_report import REPORTING_FILENAME_PREFIX
from tubular.tests.retirement_helpers import TEST_PLATFORM_NAME, fake_config_file, fake_google_secrets_file

TEST_CONFIG_FILENAME = 'test_config.yml'
TEST_GOOGLE_SECRETS_FILENAME = 'test_google_secrets.json'


def _call_script(age_in_days=1, expect_success=True):
    """
    Call the report deletion script with a generic, temporary config file.
    Returns the CliRunner.invoke results
    """
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_FILENAME, 'w') as config_f:
            fake_config_file(config_f)
        with open(TEST_GOOGLE_SECRETS_FILENAME, 'w') as secrets_f:
            fake_google_secrets_file(secrets_f)

        result = runner.invoke(
            delete_expired_reports,
            args=[
                '--config_file',
                TEST_CONFIG_FILENAME,
                '--google_secrets_file',
                TEST_GOOGLE_SECRETS_FILENAME,
                '--age_in_days',
                age_in_days
            ]
        )

        print(result)
        print(result.output)

        if expect_success:
            assert result.exit_code == 0

    return result


@patch('tubular.google_api.DriveApi.__init__')
@patch('tubular.google_api.DriveApi.walk_files')
@patch('tubular.google_api.DriveApi.delete_files')
def test_successful_report_deletion(*args):
    mock_delete_files = args[0]
    mock_walk_files = args[1]
    mock_driveapi = args[2]

    test_created_date = '2018-07-13T22:21:45.600275+00:00'
    file_prefix = '{}_{}'.format(REPORTING_FILENAME_PREFIX, TEST_PLATFORM_NAME)

    mock_walk_files.return_value = [
        {
            'id': 'folder1',
            'name': '{}.csv'.format(file_prefix),
            'createdTime': test_created_date,
        },
        {
            'id': 'folder2',
            'name': '{}_foo.csv'.format(file_prefix),
            'createdTime': test_created_date,
        },
        {
            'id': 'folder3',
            'name': '{}___bar.csv'.format(file_prefix),
            'createdTime': test_created_date,
        },
    ]
    mock_delete_files.return_value = None
    mock_driveapi.return_value = None

    result = _call_script()

    # Make sure the files were listed
    assert mock_walk_files.call_count == 1

    # Make sure we tried to delete the files
    assert mock_delete_files.call_count == 1

    assert 'Partner report deletion complete' in result.output


@patch('tubular.google_api.DriveApi.__init__')
@patch('tubular.google_api.DriveApi.walk_files')
@patch('tubular.google_api.DriveApi.delete_files')
def test_deletion_report_no_matching_files(*args):
    mock_delete_files = args[0]
    mock_walk_files = args[1]
    mock_driveapi = args[2]

    test_created_date = '2018-07-13T22:21:45.600275+00:00'
    mock_walk_files.return_value = [
        {
            'id': 'folder1',
            'name': 'not_this.csv',
            'createdTime': test_created_date,
        },
        {
            'id': 'folder2',
            'name': 'or_this.csv',
            'createdTime': test_created_date,
        },
        {
            'id': 'folder3',
            'name': 'foo.csv',
            'createdTime': test_created_date,
        },
    ]
    mock_delete_files.return_value = None
    mock_driveapi.return_value = None

    result = _call_script()

    # Make sure the files were listed
    assert mock_walk_files.call_count == 1

    # Make sure we did *not* try to delete the files - nothing to delete.
    assert mock_delete_files.call_count == 0

    assert 'Partner report deletion complete' in result.output


def test_no_config():
    runner = CliRunner()
    result = runner.invoke(delete_expired_reports)
    print(result.output)
    assert result.exit_code == ERR_NO_CONFIG
    assert 'No config file' in result.output


def test_no_secrets():
    runner = CliRunner()
    result = runner.invoke(delete_expired_reports, args=['--config_file', 'does_not_exist.yml'])
    print(result.output)
    assert result.exit_code == ERR_NO_SECRETS
    assert 'No secrets file' in result.output


def test_bad_config():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_FILENAME, 'w') as config_f:
            config_f.write(']this is bad yaml')

        with open(TEST_GOOGLE_SECRETS_FILENAME, 'w') as config_f:
            config_f.write('{this is bad json but we should not get to parsing it')

        result = runner.invoke(
            delete_expired_reports,
            args=[
                '--config_file',
                TEST_CONFIG_FILENAME,
                '--google_secrets_file',
                TEST_GOOGLE_SECRETS_FILENAME,
                '--age_in_days', 1
            ]
        )
        print(result.output)
        assert result.exit_code == ERR_BAD_CONFIG
        assert 'Failed to read' in result.output


def test_bad_secrets():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_FILENAME, 'w') as config_f:
            fake_config_file(config_f)

        with open(TEST_GOOGLE_SECRETS_FILENAME, 'w') as config_f:
            config_f.write('{this is bad json')

        tmp_output_dir = 'test_output_dir'
        os.mkdir(tmp_output_dir)

        result = runner.invoke(
            delete_expired_reports,
            args=[
                '--config_file',
                TEST_CONFIG_FILENAME,
                '--google_secrets_file',
                TEST_GOOGLE_SECRETS_FILENAME,
                '--age_in_days', 1
            ]
        )
        print(result.output)
        assert result.exit_code == ERR_BAD_SECRETS
        assert 'Failed to read' in result.output


def test_bad_age_in_days():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_FILENAME, 'w') as config_f:
            fake_config_file(config_f)

        with open(TEST_GOOGLE_SECRETS_FILENAME, 'w') as config_f:
            fake_google_secrets_file(config_f)

        result = runner.invoke(
            delete_expired_reports,
            args=[
                '--config_file',
                TEST_CONFIG_FILENAME,
                '--google_secrets_file',
                TEST_GOOGLE_SECRETS_FILENAME,
                '--age_in_days', -1000
            ]
        )
        print(result.output)
        assert result.exit_code == ERR_BAD_AGE
        assert 'must be a positive integer' in result.output


@patch('tubular.google_api.DriveApi.__init__')
@patch('tubular.google_api.DriveApi.delete_files_older_than')
def test_deletion_error(*args):
    mock_delete_old_reports = args[0]
    mock_drive_init = args[1]

    mock_delete_old_reports.side_effect = Exception()
    mock_drive_init.return_value = None

    result = _call_script(expect_success=False)

    assert result.exit_code == ERR_DELETING_REPORTS
    assert 'Unexpected error occurred' in result.output
