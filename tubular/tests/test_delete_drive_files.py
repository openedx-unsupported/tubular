# coding=utf-8
"""
Test the delete_drive_files.py script
"""

from click.testing import CliRunner
from mock import patch

from tubular.scripts.delete_drive_files import (
    ERR_NO_CONFIG,
    ERR_BAD_CONFIG,
    ERR_NO_SECRETS,
    ERR_BAD_SECRETS,
    ERR_DELETING_FILES,
    ERR_NO_FILE_IDS,
    ERR_TOO_MANY_FILE_IDS,
    delete_files
)
from tubular.tests.retirement_helpers import fake_config_file, fake_google_secrets_file, FAKE_ORGS

TEST_CONFIG_YML_NAME = 'test_config.yml'
TEST_GOOGLE_SECRETS_FILENAME = 'test_google_secrets.json'


def _call_script(expect_success=True, config_orgs=None, file_ids=None):
    """
    Call the retired learner script with generic, temporary config files and specified file IDs.
    Returns the CliRunner.invoke results.
    """
    if config_orgs is None:
        config_orgs = FAKE_ORGS

    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_YML_NAME, 'w') as config_f:
            fake_config_file(config_f, config_orgs)
        with open(TEST_GOOGLE_SECRETS_FILENAME, 'w') as secrets_f:
            fake_google_secrets_file(secrets_f)

        cmd_args = [
            '--config_file',
            TEST_CONFIG_YML_NAME,
            '--google_secrets_file',
            TEST_GOOGLE_SECRETS_FILENAME,
        ]
        if file_ids:
            for file_id in file_ids:
                cmd_args.extend(['--file_id', file_id])

        result = runner.invoke(
            delete_files,
            args=cmd_args
        )

        print(result)
        print(result.output)

        if expect_success:
            assert result.exit_code == 0

    return result


@patch('tubular.google_api.DriveApi.__init__')
@patch('tubular.google_api.DriveApi.delete_files')
def test_successful_report(*args):
    mock_delete_files = args[0]
    mock_driveapi = args[1]

    mock_delete_files.return_value = None
    mock_driveapi.return_value = None

    result = _call_script(file_ids=['fake_file_id1', 'fake_file_id2'])

    # Make sure we tried to delete the files
    assert mock_delete_files.call_count == 1

    assert 'All files deleted successfully.' in result.output


@patch('tubular.google_api.DriveApi.__init__')
def test_unknown_error(*args):
    mock_driveapi = args[0]
    mock_driveapi.side_effect = Exception('Unknown error.')

    result = _call_script(expect_success=False, file_ids=['fake_file_id1'])
    print(result.output)
    assert result.exit_code == ERR_DELETING_FILES
    assert 'Unexpected error occurred' in result.output


def test_no_file_ids():
    result = _call_script(expect_success=False)
    print(result.output)
    assert result.exit_code == ERR_NO_FILE_IDS
    assert 'No file IDs were specified' in result.output


def test_too_many_file_ids():
    result = _call_script(expect_success=False, file_ids=['fake_file_id{}'.format(i) for i in range(150)])
    print(result.output)
    assert result.exit_code == ERR_TOO_MANY_FILE_IDS
    assert 'Too many file IDs specfied' in result.output


def test_no_config():
    runner = CliRunner()
    result = runner.invoke(delete_files)
    print(result.output)
    assert result.exit_code == ERR_NO_CONFIG
    assert 'No config file' in result.output


def test_no_secrets():
    runner = CliRunner()
    result = runner.invoke(delete_files, args=['--config_file', 'does_not_exist.yml'])
    print(result.output)
    assert result.exit_code == ERR_NO_SECRETS
    assert 'No secrets file' in result.output


def test_bad_config():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_YML_NAME, 'w') as config_f:
            config_f.write(']this is bad yaml')

        with open(TEST_GOOGLE_SECRETS_FILENAME, 'w') as config_f:
            config_f.write('{this is bad json but we should not get to parsing it')

        result = runner.invoke(
            delete_files,
            args=[
                '--config_file',
                TEST_CONFIG_YML_NAME,
                '--google_secrets_file',
                TEST_GOOGLE_SECRETS_FILENAME,
                '--file_id',
                'a_fake_file_id'
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

        result = runner.invoke(
            delete_files,
            args=[
                '--config_file',
                TEST_CONFIG_YML_NAME,
                '--google_secrets_file',
                TEST_GOOGLE_SECRETS_FILENAME,
                '--file_id',
                'a_fake_file_id'
            ]
        )
        print(result.output)
        assert result.exit_code == ERR_BAD_SECRETS
        assert 'Failed to read' in result.output
