"""
Test the retirement_archive_and_cleanup.py script
"""


from mock import patch, DEFAULT

from click.testing import CliRunner

from tubular.scripts.retirement_archive_and_cleanup import (
    ERR_ARCHIVING,
    ERR_BAD_CONFIG,
    ERR_DELETING,
    ERR_FETCHING,
    ERR_NO_CONFIG,
    ERR_SETUP_FAILED,
    archive_and_cleanup
)
from tubular.tests.retirement_helpers import fake_config_file, get_fake_user_retirement


def _call_script(cool_off_days=37):
    """
    Call the archive script with the given params and a generic config file.
    Returns the CliRunner.invoke results
    """
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open('test_config.yml', 'w') as f:
            fake_config_file(f)

        result = runner.invoke(
            archive_and_cleanup,
            args=[
                '--config_file', 'test_config.yml',
                '--cool_off_days', cool_off_days
            ]
        )
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
@patch('tubular.scripts.retirement_archive_and_cleanup.S3Connection')
@patch('tubular.scripts.retirement_archive_and_cleanup.Key')
@patch.multiple(
    'tubular.edx_api.LmsApi',
    get_learners_by_date_and_status=DEFAULT,
    bulk_cleanup_retirements=DEFAULT
)
def test_successful(*args, **kwargs):
    mock_get_access_token = args[2]
    mock_s3connection_class = args[1]
    mock_get_learners = kwargs['get_learners_by_date_and_status']
    mock_bulk_cleanup_retirements = kwargs['bulk_cleanup_retirements']

    mock_get_learners.return_value = fake_learners_to_retire()

    result = _call_script()

    # Called once to get the LMS token
    assert mock_get_access_token.call_count == 1
    mock_get_learners.assert_called_once()
    mock_bulk_cleanup_retirements.assert_called_once_with(['test1', 'test2', 'test3'])
    mock_s3connection_class.assert_called_once_with(host='s3.fake_region.amazonaws.com')

    assert result.exit_code == 0
    assert 'Archive and cleanup complete' in result.output


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
