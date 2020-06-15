#! /usr/bin/env python3
"""
Command-line script to bulk archive and cleanup retired learners from LMS
"""

from functools import partial
from os import path
import datetime
import gzip
import json
import logging
import sys

import backoff
import click
from boto.s3.connection import S3Connection
from boto.s3.key import Key
from boto.exception import BotoClientError, BotoServerError
from six import text_type

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

# pylint: disable=wrong-import-position
from tubular.scripts.helpers import (
    _config_or_exit,
    _fail,
    _fail_exception,
    _log,
    _setup_lms_api_or_exit
)

SCRIPT_SHORTNAME = 'Archive and Cleanup'

# Return codes for various fail cases
ERR_NO_CONFIG = -1
ERR_BAD_CONFIG = -2
ERR_FETCHING = -3
ERR_ARCHIVING = -4
ERR_DELETING = -5
ERR_SETUP_FAILED = -5

LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)
FAIL_EXCEPTION = partial(_fail_exception, SCRIPT_SHORTNAME)
CONFIG_OR_EXIT = partial(_config_or_exit, FAIL_EXCEPTION, ERR_BAD_CONFIG)
SETUP_LMS_OR_EXIT = partial(_setup_lms_api_or_exit, FAIL, ERR_SETUP_FAILED)

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


def _fetch_learners_to_archive_or_exit(config, start_date, end_date, initial_state):
    """
    Makes the call to fetch learners to be cleaned up, returns the list of learners or exits.
    """
    LOG('Fetching users in state {} created from {} to {}'.format(initial_state, start_date, end_date))
    try:
        return config['LMS'].get_learners_by_date_and_status(initial_state, start_date, end_date)
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_FETCHING, 'Unexpected error occurred fetching users to update!', exc)


def _on_s3_backoff(details):
    """
    Callback that is called when backoff... backs off
    """
    LOG("Backing off {wait:0.1f} seconds after {tries} tries calling function {target}".format(**details))


@backoff.on_exception(
    backoff.expo,
    (
            BotoClientError,
            BotoServerError
    ),
    on_backoff=lambda details: _on_s3_backoff(details),  # pylint: disable=unnecessary-lambda,
    max_time=120,  # 2 minutes
)
def _upload_to_s3(config, filename):
    """
    Upload the archive file to S3
    """
    try:
        s3_credentials = ()
        if 'access_key' in config['s3_archive']:
            s3_credentials = (
                config['s3_archive']['access_key'],
                config['s3_archive']['secret_key'],
            )

        s3_connection = S3Connection(
            *s3_credentials,
            host='s3.{}.amazonaws.com'.format(config['s3_archive']['region'])
        )

        datestr = datetime.datetime.now().strftime('%Y/%m/')

        bucket = s3_connection.get_bucket(config['s3_archive']['bucket_name'])
        key = Key(bucket, datestr + filename)
        key.set_contents_from_filename(filename)
    except Exception as exc:
        LOG(text_type(exc))
        raise


def _format_datetime_for_athena(timestamp):
    """
    Takes a JSON serialized timestamp string and returns a format of it that is queryable as a datetime in Athena
    """
    return timestamp.replace('T', ' ').rstrip('Z')


def _archive_retirements_or_exit(config, learners):
    """
    Creates an archive file with all of the retirements and uploads it to S3

    The format of learners from LMS should be a list of these:
    {
    'id': 46, # This is the UserRetirementStatus ID!
    'user':
        {
        'id': 5213599,  # THIS is the LMS User ID
        'username': 'retired__user_88ad587896920805c26041a2e75c767c75471ee9',
        'email': 'retired__user_d08919da55a0e03c032425567e4a33e860488a96@retired.invalid',
        'profile':
            {
            'id': 2842382,
            'name': ''
            }
        },
    'current_state':
    {
        'id': 41,
        'state_name': 'COMPLETE',
        'state_execution_order': 13
    },
    'last_state': {
        'id': 1,
        'state_name': 'PENDING',
        'state_execution_order': 1
    },
    'created': '2018-10-18T20:35:52.349757Z',  # This is the UserRetirementStatus creation date
    'modified': '2018-10-18T20:35:52.350050Z',  # This is the UserRetirementStatus last touched date
    'original_username': 'retirement_test',
    'original_email': 'orig@foo.invalid',
    'original_name': 'Retirement Test',
    'retired_username': 'retired__user_88ad587896920805c26041a2e75c767c75471ee9',
    'retired_email': 'retired__user_d08919da55a0e03c032425567e4a33e860488a96@retired.invalid'
    }
    """
    LOG('Archiving retirements for {} learners to {}'.format(len(learners), config['s3_archive']['bucket_name']))
    try:
        now = datetime.datetime.utcnow()
        filename = 'retirement_archive_{}.json.gz'.format(now.strftime('%Y_%d_%m_%H_%M_%S'))

        # The file format is one JSON object per line with the newline as a separator. This allows for
        # easy queries via AWS Athena if we need to confirm learner deletion.
        with gzip.open(filename, 'wt') as out:
            for learner in learners:
                user = {
                    'user_id': learner['user']['id'],
                    'original_username': learner['original_username'],
                    'original_email': learner['original_email'],
                    'original_name': learner['original_name'],
                    'retired_username': learner['retired_username'],
                    'retired_email': learner['retired_email'],
                    'retirement_request_date': _format_datetime_for_athena(learner['created']),
                    'last_modified_date': _format_datetime_for_athena(learner['modified']),
                }
                json.dump(user, out)
                out.write("\n")

        _upload_to_s3(config, filename)
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_ARCHIVING, 'Unexpected error occurred archiving retirements!', exc)


def _cleanup_retirements_or_exit(config, learners):
    """
    Bulk deletes the retirements for this run
    """
    LOG('Cleaning up retirements for {} learners'.format(len(learners)))
    try:
        usernames = [l['original_username'] for l in learners]
        config['LMS'].bulk_cleanup_retirements(usernames)
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_DELETING, 'Unexpected error occurred deleting retirements!', exc)


@click.command()
@click.option(
    '--config_file',
    help='YAML file that contains retirement-related configuration for this environment.'
)
@click.option(
    '--cool_off_days',
    help='Number of days a retirement should exist before being archived and deleted.',
    type=int,
    default=37  # 7 days before retirement, 30 after
)
def archive_and_cleanup(config_file, cool_off_days):
    """
    Cleans up UserRetirementStatus rows in LMS by:
    1- Getting all rows currently in COMPLETE that were created --cool_off_days ago or more
    2- Archiving them to S3 in an Athena-queryable format
    3- Deleting them from LMS (by username)
    """
    try:
        LOG('Starting bulk update script: Config: {}'.format(config_file))

        if not config_file:
            FAIL(ERR_NO_CONFIG, 'No config file passed in.')

        config = CONFIG_OR_EXIT(config_file)
        SETUP_LMS_OR_EXIT(config)

        # This date is just a bogus "earliest possible value" since the call requires one
        start_date = datetime.datetime.strptime('2018-01-01', '%Y-%m-%d')
        end_date = datetime.datetime.utcnow().date() - datetime.timedelta(days=cool_off_days)

        LOG('Fetching learners in COMPLETE status from {} to {}.'.format(start_date, end_date))
        learners = _fetch_learners_to_archive_or_exit(config, start_date, end_date, 'COMPLETE')

        if learners:
            _archive_retirements_or_exit(config, learners)
            _cleanup_retirements_or_exit(config, learners)
            LOG('Archive and cleanup complete')
        else:
            LOG('No learners found!')
    except Exception as exc:
        LOG(text_type(exc))
        raise


if __name__ == '__main__':
    # pylint: disable=unexpected-keyword-arg, no-value-for-parameter
    archive_and_cleanup(auto_envvar_prefix='RETIREMENT')
