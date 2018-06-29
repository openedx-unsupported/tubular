# coding=utf-8
"""
Test the retire_one_learner.py script
"""
from __future__ import print_function

import csv
import os
from datetime import date
from random import randrange

from mock import patch, DEFAULT

from click.testing import CliRunner

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
    generate_report
)
from tubular.tests.retirement_helpers import fake_config_file, fake_google_secrets_file


def _call_script(expect_success=True, orgs_to_check=None):
    """
    Call the retired learner script with the given username and a generic, temporary config file.
    Returns the CliRunner.invoke results
    """
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open('test_config.yml', 'w') as config_f:
            fake_config_file(config_f)
        with open('test_google_secrets.json', 'w') as secrets_f:
            fake_google_secrets_file(secrets_f)

        tmp_output_dir = 'test_output_dir'
        os.mkdir(tmp_output_dir)

        result = runner.invoke(
            generate_report,
            args=[
                '--config_file',
                'test_config.yml',
                '--google_secrets_file',
                'test_google_secrets.json',
                '--output_dir',
                tmp_output_dir
            ]
        )

        print(result)
        print(result.output)

        if expect_success:
            assert result.exit_code == 0

            if orgs_to_check is None:
                orgs_to_check = ['Org1X', 'Org2X', 'Org3X']

            for org in orgs_to_check:
                outfile = os.path.join(tmp_output_dir, '{}_{}.csv'.format(org, date.today().isoformat()))

                with open(outfile, 'r') as csvfile:
                    reader = csv.DictReader(csvfile)
                    rows = []
                    for row in reader:

                        # Check username value is in the right place
                        assert 'username' in row['original_username']

                        # Check email value is in the right place
                        assert 'invalid' in row['original_email']

                        # Check name value is in the right place
                        assert '阿碧' in row['original_name']

                        rows.append(row)

                # Confirm that there are rows at all
                assert len(rows)
    return result


def _fake_retirement_report_user(seed_val, rand_orgs=None):
    """
    Creates unique user to populate a fake report with.
    - seed_val is a number or other unique value for this user, will be formatted into
      user values to make sure they're distinct.
    - rand_orgs, if given, should be a list of orgs that will be chosen from randomly
      for the user. Between 1 and len(rand_orgs) orgs will be chosen.
    """
    if rand_orgs is None:
        rand_orgs = ['org1', 'org2', 'org3']

    num_user_orgs = randrange(0, len(rand_orgs))
    user_orgs = rand_orgs[:num_user_orgs + 1]

    return {
        'original_username': 'username_{}'.format(seed_val),
        'original_email': 'user_{}@foo.invalid'.format(seed_val),
        'original_name': '阿碧 {}'.format(seed_val),
        'orgs': user_orgs
    }


def _fake_retirement_report(num_users=10):
    """
    Fake the output of a retirement report with unique users
    """
    return [_fake_retirement_report_user(i) for i in range(num_users)]


@patch('tubular.google_api.DriveApi.__init__')
@patch('tubular.google_api.DriveApi.create_file_in_folder')
@patch('tubular.edx_api.BaseApiClient.get_access_token')
@patch.multiple(
    'tubular.edx_api.LmsApi',
    retirement_partner_report=DEFAULT,
    retirement_partner_cleanup=DEFAULT
)
def test_successful_report(*args, **kwargs):
    mock_get_access_token = args[0]
    mock_create_files = args[1]
    mock_driveapi = args[2]
    mock_retirement_report = kwargs['retirement_partner_report']
    mock_retirement_cleanup = kwargs['retirement_partner_cleanup']

    mock_get_access_token.return_value = ('THIS_IS_A_JWT', None)
    mock_create_files.return_value = True
    mock_driveapi.return_value = None
    mock_retirement_report.return_value = _fake_retirement_report()

    result = _call_script()

    # Make sure we're getting the LMS token
    assert mock_get_access_token.called_once()

    # Make sure that we get the report
    assert mock_retirement_report.called_once()

    # Make sure we tried to upload the files
    assert mock_create_files.call_count == 3

    # Make sure we tried to remove the users from the queue
    assert mock_retirement_report.called_once()
    assert mock_retirement_cleanup.called_with(
        [u['original_username'] for u in mock_retirement_report.return_value]
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
        with open('test_config.yml', 'w') as config_f:
            config_f.write('irrelevant')

        with open('test_google_secrets.json', 'w') as config_f:
            config_f.write('irrelevant')

        result = runner.invoke(
            generate_report,
            args=[
                '--config_file',
                'test_config.yml',
                '--google_secrets_file',
                'test_google_secrets.json'
            ]
        )
    print(result.output)
    assert result.exit_code == ERR_NO_OUTPUT_DIR
    assert 'No output_dir' in result.output


def test_bad_config():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open('test_config.yml', 'w') as config_f:
            config_f.write(']this is bad yaml')

        with open('test_google_secrets.json', 'w') as config_f:
            config_f.write('{this is bad json but we should not get to parsing it')

        tmp_output_dir = 'test_output_dir'
        os.mkdir(tmp_output_dir)

        result = runner.invoke(
            generate_report,
            args=[
                '--config_file',
                'test_config.yml',
                '--google_secrets_file',
                'test_google_secrets.json',
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
        with open('test_config.yml', 'w') as config_f:
            fake_config_file(config_f)

        with open('test_google_secrets.json', 'w') as config_f:
            config_f.write('{this is bad json')

        tmp_output_dir = 'test_output_dir'
        os.mkdir(tmp_output_dir)

        result = runner.invoke(
            generate_report,
            args=[
                '--config_file',
                'test_config.yml',
                '--google_secrets_file',
                'test_google_secrets.json',
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
        with open('test_config.yml', 'w') as config_f:
            fake_config_file(config_f)

        with open('test_google_secrets.json', 'w') as config_f:
            fake_google_secrets_file(config_f)

        result = runner.invoke(
            generate_report,
            args=[
                '--config_file',
                'test_config.yml',
                '--google_secrets_file',
                'test_google_secrets.json',
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
    assert mock_get_access_token.called_once()
    assert result.exit_code == ERR_SETUP_FAILED


@patch('tubular.edx_api.BaseApiClient.get_access_token')
@patch.multiple(
    'tubular.edx_api.LmsApi',
    retirement_partner_report=DEFAULT)
def test_fetching_learners_failed(*args, **kwargs):
    mock_get_access_token = args[0]
    mock_retirement_report = kwargs['retirement_partner_report']

    mock_get_access_token.return_value = ('THIS_IS_A_JWT', None)
    mock_retirement_report.side_effect = Exception('failed to get learners')

    result = _call_script(expect_success=False)

    assert result.exit_code == ERR_FETCHING_LEARNERS
    assert 'failed to get learners' in result.output


@patch('tubular.edx_api.BaseApiClient.get_access_token')
@patch.multiple(
    'tubular.edx_api.LmsApi',
    retirement_partner_report=DEFAULT)
def test_unknown_org(*args, **kwargs):
    mock_get_access_token = args[0]
    mock_retirement_report = kwargs['retirement_partner_report']

    mock_get_access_token.return_value = ('THIS_IS_A_JWT', None)

    orgs = ['orgA', 'orgB']

    mock_retirement_report.return_value = [_fake_retirement_report_user(i, orgs) for i in range(10)]

    result = _call_script(expect_success=False)

    assert result.exit_code == ERR_UNKNOWN_ORG
    assert 'orgA' in result.output


@patch('tubular.edx_api.BaseApiClient.get_access_token')
@patch('csv.DictWriter')
@patch('tubular.edx_api.LmsApi.retirement_partner_report')
def test_reporting_error(*args):
    mock_retirement_report = args[0]
    mock_dictwriter = args[1]
    mock_get_access_token = args[2]

    error_msg = 'Fake unable to write csv'

    mock_get_access_token.return_value = ('THIS_IS_A_JWT', None)
    mock_dictwriter.side_effect = Exception(error_msg)
    mock_retirement_report.return_value = _fake_retirement_report()

    result = _call_script(expect_success=False)

    assert result.exit_code == ERR_REPORTING
    assert error_msg in result.output


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
    mock_retirement_report = kwargs['retirement_partner_report']
    mock_retirement_cleanup = kwargs['retirement_partner_cleanup']

    mock_get_access_token.return_value = ('THIS_IS_A_JWT', None)
    mock_create_files.return_value = True
    mock_driveapi.return_value = None
    mock_retirement_report.return_value = _fake_retirement_report()
    mock_retirement_cleanup.side_effect = Exception('Mock cleanup exception')

    result = _call_script(expect_success=False)

    assert mock_retirement_cleanup.called_with(
        [u['original_username'] for u in mock_retirement_report.return_value]
    )

    assert result.exit_code == ERR_CLEANUP
    assert 'Rows may be stuck in processing state!' in result.output
