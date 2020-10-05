# coding=utf-8
"""
Test the bulk_delete_segment_users.py script
"""


from click.testing import CliRunner
from mock import patch

from tubular.scripts.bulk_delete_segment_users import (
    ERR_NO_CONFIG,
    ERR_BAD_CONFIG,
    ERR_NO_CSV_FILE,
    ERR_DELETING_USERS,
    bulk_delete_segment_users
)
from tubular.tests.retirement_helpers import fake_config_file, FAKE_ORGS


TEST_CONFIG_YML_NAME = 'test_config.yml'
TEST_RETIRED_USERS_CSV_NAME = 'test_users_to_delete.yml'


def _call_script(expect_success=True, config_orgs=None, learners_to_delete=None):
    """
    Call the retired learner script with generic, temporary config files and specified learners.
    Returns the CliRunner.invoke results.
    """
    if config_orgs is None:
        config_orgs = FAKE_ORGS

    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_YML_NAME, 'w') as config_f:
            fake_config_file(config_f, config_orgs)

        if learners_to_delete:
            with open(TEST_RETIRED_USERS_CSV_NAME, 'w') as users_f:
                for learner in learners_to_delete:
                    users_f.write(','.join(learner))

        cmd_args = [
            '--config_file',
            TEST_CONFIG_YML_NAME,
            '--retired_users_csv',
            TEST_RETIRED_USERS_CSV_NAME,
        ]

        result = runner.invoke(
            bulk_delete_segment_users,
            args=cmd_args
        )

        print(result)
        print(result.output)

        if expect_success:
            assert result.exit_code == 0

    return result


@patch('tubular.segment_api.SegmentApi.delete_and_suppress_learners')
def test_successful_deletion(*args):
    mock_delete_learners = args[0]

    mock_delete_learners.return_value = None

    _call_script(
        learners_to_delete=[
            ['1', '14', 'test_username1', 'fake_ecom_id1']
        ]
    )

    # Make sure we tried to delete the learners.
    assert mock_delete_learners.call_count == 1


@patch('tubular.segment_api.SegmentApi.delete_and_suppress_learners')
def test_unknown_error(*args):
    mock_delete_learners = args[0]
    mock_delete_learners.side_effect = Exception('Unknown error.')

    result = _call_script(expect_success=False, learners_to_delete=[['1', '2', 'test1', 'test2']])
    print(result.output)
    assert result.exit_code == ERR_DELETING_USERS
    assert 'Unexpected error occurred' in result.output


def test_no_config():
    runner = CliRunner()
    result = runner.invoke(bulk_delete_segment_users)
    print(result.output)
    assert result.exit_code == ERR_NO_CONFIG
    assert 'No config file' in result.output


def test_bad_config():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_YML_NAME, 'w') as config_f:
            config_f.write(']this is bad yaml')

        result = runner.invoke(
            bulk_delete_segment_users,
            args=[
                '--config_file',
                TEST_CONFIG_YML_NAME,
                '--retired_users_csv',
                TEST_RETIRED_USERS_CSV_NAME
            ]
        )
        print(result.output)
        assert result.exit_code == ERR_BAD_CONFIG
        assert 'Failed to read' in result.output


def test_no_users_csv_file():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open(TEST_CONFIG_YML_NAME, 'w') as config_f:
            fake_config_file(config_f, [])

        result = runner.invoke(
            bulk_delete_segment_users,
            args=[
                '--config_file',
                TEST_CONFIG_YML_NAME,
            ]
        )
        print(result.output)
        assert result.exit_code == ERR_NO_CSV_FILE
        assert 'No users CSV file passed in' in result.output
