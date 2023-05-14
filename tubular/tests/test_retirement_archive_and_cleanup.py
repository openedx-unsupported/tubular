"""
Test the retirement_archive_and_cleanup.py script
"""


import datetime

import boto3
from click.testing import CliRunner
from mock import DEFAULT, call, patch
from moto import mock_ec2, mock_s3

from tubular.scripts.retirement_archive_and_cleanup import (
    ERR_ARCHIVING, ERR_BAD_CLI_PARAM, ERR_BAD_CONFIG, ERR_DELETING,
    ERR_FETCHING, ERR_NO_CONFIG, ERR_SETUP_FAILED, archive_and_cleanup)
from tubular.tests.retirement_helpers import (
    fake_config_file, get_fake_user_retirement
)


def _call_script(cool_off_days=37, batch_size=None, dry_run=None, start_date=None, end_date=None):
    """
    Call the archive script with the given params and a generic config file.
    Returns the CliRunner.invoke results
    """
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open('test_config.yml', 'w') as f:
            fake_config_file(f)

        base_args = [
            '--config_file', 'test_config.yml',
            '--cool_off_days', cool_off_days,
        ]
        if batch_size:
            base_args += ['--batch_size', batch_size]
        if dry_run:
            base_args += ['--dry_run', dry_run]
        if start_date:
            base_args += ['--start_date', start_date]
        if end_date:
            base_args += ['--end_date', end_date]

        result = runner.invoke(archive_and_cleanup, args=base_args)
    print(result)
    print(result.output)
    return result


def _fake_learner(ordinal):
    """
    Creates a simple fake learner
    """
    return get_fake_user_retirement(
        user_id=ordinal,
        original_username='test{}'.format(ordinal),
        original_email='test{}@edx.invalid'.format(ordinal),
        original_name='test {}'.format(ordinal),
        retired_username='retired_{}'.format(ordinal),
        retired_email='retired_test{}@edx.invalid'.format(ordinal),
        last_state_name='COMPLETE'
    )


def fake_learners_to_retire():
    """
    A simple hard-coded list of fake learners
    """
    return [
        _fake_learner(1),
        _fake_learner(2),
        _fake_learner(3)
    ]


@patch('tubular.edx_api.BaseApiClient.get_access_token', return_value=('THIS_IS_A_JWT', None))
@patch.multiple(
    'tubular.edx_api.LmsApi',
    get_learners_by_date_and_status=DEFAULT,
    bulk_cleanup_retirements=DEFAULT
)
@mock_s3
def test_successful(*args, **kwargs):
    conn = boto3.resource('s3')
    conn.create_bucket(Bucket="fake_test_bucket")

    mock_get_access_token = args[0]
    mock_get_learners = kwargs['get_learners_by_date_and_status']
    mock_bulk_cleanup_retirements = kwargs['bulk_cleanup_retirements']

    mock_get_learners.return_value = fake_learners_to_retire()

    result = _call_script()

    # Called once to get the LMS token
    assert mock_get_access_token.call_count == 1
    mock_get_learners.assert_called_once()
    mock_bulk_cleanup_retirements.assert_called_once_with(
        ['test1', 'test2', 'test3'])

    assert result.exit_code == 0
    assert 'Archive and cleanup complete' in result.output


@patch('tubular.edx_api.BaseApiClient.get_access_token', return_value=('THIS_IS_A_JWT', None))
@patch.multiple(
    'tubular.edx_api.LmsApi',
    get_learners_by_date_and_status=DEFAULT,
    bulk_cleanup_retirements=DEFAULT
)
@mock_ec2
@mock_s3
def test_successful_with_batching(*args, **kwargs):
    conn = boto3.resource('s3')
    conn.create_bucket(Bucket="fake_test_bucket")

    mock_get_access_token = args[0]
    mock_get_learners = kwargs['get_learners_by_date_and_status']
    mock_bulk_cleanup_retirements = kwargs['bulk_cleanup_retirements']

    mock_get_learners.return_value = fake_learners_to_retire()

    result = _call_script(batch_size=2)

    # Called once to get the LMS token
    assert mock_get_access_token.call_count == 1
    mock_get_learners.assert_called_once()
    get_learner_calls = [call(['test1', 'test2']), call(['test3'])]
    mock_bulk_cleanup_retirements.assert_has_calls(get_learner_calls)

    assert result.exit_code == 0
    assert 'Archive and cleanup complete for batch #1' in result.output
    assert 'Archive and cleanup complete for batch #2' in result.output


@patch('tubular.edx_api.BaseApiClient.get_access_token', return_value=('THIS_IS_A_JWT', None))
@patch.multiple(
    'tubular.edx_api.LmsApi',
    get_learners_by_date_and_status=DEFAULT,
    bulk_cleanup_retirements=DEFAULT
)
@mock_s3
def test_successful_dry_run(*args, **kwargs):
    mock_get_access_token = args[0]
    mock_get_learners = kwargs['get_learners_by_date_and_status']
    mock_bulk_cleanup_retirements = kwargs['bulk_cleanup_retirements']

    mock_get_learners.return_value = fake_learners_to_retire()

    result = _call_script(dry_run=True)

    # Called once to get the LMS token
    assert mock_get_access_token.call_count == 1
    mock_get_learners.assert_called_once()
    mock_bulk_cleanup_retirements.assert_not_called()

    assert result.exit_code == 0
    assert 'Dry run. Skipping the step to upload data to' in result.output
    assert 'This is a dry-run. Exiting before any retirements are cleaned up' in result.output


def test_no_config():
    runner = CliRunner()
    result = runner.invoke(
        archive_and_cleanup,
        args=[
            '--cool_off_days', 37
        ]
    )
    assert result.exit_code == ERR_NO_CONFIG
    assert 'No config file passed in.' in result.output


def test_bad_config():
    runner = CliRunner()
    result = runner.invoke(
        archive_and_cleanup,
        args=[
            '--config_file', 'does_not_exist.yml',
            '--cool_off_days', 37
        ]
    )
    assert result.exit_code == ERR_BAD_CONFIG
    assert 'does_not_exist.yml' in result.output


@patch('tubular.edx_api.BaseApiClient.get_access_token', return_value=('THIS_IS_A_JWT', None))
@patch('tubular.edx_api.LmsApi.__init__', side_effect=Exception)
def test_setup_failed(*_):
    result = _call_script()
    assert result.exit_code == ERR_SETUP_FAILED


@patch('tubular.edx_api.BaseApiClient.get_access_token', return_value=('THIS_IS_A_JWT', None))
@patch('tubular.edx_api.LmsApi.get_learners_by_date_and_status', side_effect=Exception)
def test_bad_fetch(*_):
    result = _call_script()
    assert result.exit_code == ERR_FETCHING
    assert 'Unexpected error occurred fetching users to update!' in result.output


@patch('tubular.edx_api.BaseApiClient.get_access_token', return_value=('THIS_IS_A_JWT', None))
@patch('tubular.edx_api.LmsApi.get_learners_by_date_and_status', return_value=fake_learners_to_retire())
@patch('tubular.edx_api.LmsApi.bulk_cleanup_retirements', side_effect=Exception)
@patch('tubular.scripts.retirement_archive_and_cleanup._upload_to_s3')
def test_bad_lms_deletion(*_):
    result = _call_script()
    assert result.exit_code == ERR_DELETING
    assert 'Unexpected error occurred deleting retirements!' in result.output


@patch('tubular.edx_api.BaseApiClient.get_access_token', return_value=('THIS_IS_A_JWT', None))
@patch('tubular.edx_api.LmsApi.get_learners_by_date_and_status', return_value=fake_learners_to_retire())
@patch('tubular.edx_api.LmsApi.bulk_cleanup_retirements')
@patch('tubular.scripts.retirement_archive_and_cleanup._upload_to_s3', side_effect=Exception)
def test_bad_s3_upload(*_):
    result = _call_script()
    assert result.exit_code == ERR_ARCHIVING
    assert 'Unexpected error occurred archiving retirements!' in result.output


@patch('tubular.edx_api.BaseApiClient.get_access_token', return_value=('THIS_IS_A_JWT', None))
def test_conflicting_dates(*_):
    result = _call_script(start_date=datetime.datetime(
        2021, 10, 10), end_date=datetime.datetime(2018, 10, 10))
    assert result.exit_code == ERR_BAD_CLI_PARAM
    assert 'Conflicting start and end dates passed on CLI' in result.output


@patch('tubular.edx_api.BaseApiClient.get_access_token', return_value=('THIS_IS_A_JWT', None))
@patch(
    'tubular.scripts.retirement_archive_and_cleanup._get_utc_now',
    return_value=datetime.datetime(2021, 2, 2, 0, 0)
)
def test_conflicting_cool_off_date(*_):
    result = _call_script(
        cool_off_days=10,
        start_date=datetime.datetime(2021, 1, 1), end_date=datetime.datetime(2021, 2, 1)
    )
    assert result.exit_code == ERR_BAD_CLI_PARAM
    assert 'End date cannot occur within the cool_off_days period' in result.output