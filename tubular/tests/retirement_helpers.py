"""
Common functionality for retirement related tests
"""

import yaml


TEST_RETIREMENT_PIPELINE = [
    ['RETIRING_FORUMS', 'FORUMS_COMPLETE', 'LMS', 'retirement_retire_forum'],
    ['RETIRING_EMAIL_LISTS', 'EMAIL_LISTS_COMPLETE', 'LMS', 'retirement_retire_mailings'],
    ['RETIRING_ENROLLMENTS', 'ENROLLMENTS_COMPLETE', 'LMS', 'retirement_unenroll'],
    ['RETIRING_LMS', 'LMS_COMPLETE', 'LMS', 'retirement_lms_retire']
]

TEST_RETIREMENT_END_STATES = [state[1] for state in TEST_RETIREMENT_PIPELINE]
TEST_RETIREMENT_QUEUE_STATES = ['PENDING'] + TEST_RETIREMENT_END_STATES


def fake_config_file(f):
    """
    Create a config file for a single test. Combined with CliRunner.isolated_filesystem() to
    ensure the file lifetime is limited to the test. See _call_script for usage.
    """

    config = {
        'client_id': 'bogus id',
        'client_secret': 'supersecret',
        'base_urls': {
            'credentials': 'https://credentials.stage.edx.org/',
            'lms': 'https://stage-edx-edxapp.edx.org/',
            'ecommerce': 'https://ecommerce.stage.edx.org/'
        },
        'retirement_pipeline': TEST_RETIREMENT_PIPELINE
    }

    yaml.safe_dump(config, f)
