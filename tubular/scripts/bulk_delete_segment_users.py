#! /usr/bin/env python3
"""
Command-line script to bulk delete users from Segment.
"""


from functools import partial
from os import path
import csv
import logging
import sys

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.segment_api import SegmentApi  # pylint: disable=wrong-import-position
# pylint: disable=wrong-import-position
from tubular.scripts.helpers import (
    _config_or_exit,
    _fail,
    _fail_exception,
    _log
)

DEFAULT_CHUNK_SIZE = 5000

# Return codes for various fail cases
ERR_NO_CONFIG = -1
ERR_BAD_CONFIG = -2
ERR_NO_CSV_FILE = -3
ERR_DELETING_USERS = -4

SCRIPT_SHORTNAME = 'bulk_delete_segment_users'
LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)
FAIL_EXCEPTION = partial(_fail_exception, SCRIPT_SHORTNAME)
CONFIG_OR_EXIT = partial(_config_or_exit, FAIL_EXCEPTION, ERR_BAD_CONFIG)

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


@click.command("bulk_delete_segment_users")
@click.option(
    '--dry_run',
    is_flag=True,
    help='Print actions that would be performed without deleting anyone.'
)
@click.option(
    '--config_file',
    help='YAML file that contains retirement-related configuration for this environment.'
)
@click.option(
    '--retired_users_csv',
    help='CSV file with all users to delete from Segment.'
)
@click.option(
    '--chunk_size',
    default=DEFAULT_CHUNK_SIZE,
    help='Maximum number of Segment deletions to perform in each deletion request.'
)
def bulk_delete_segment_users(dry_run, config_file, retired_users_csv, chunk_size):
    """
    Deletes the users in the CSV file from Segment.
    """
    if not config_file:
        FAIL(ERR_NO_CONFIG, 'No config file passed in.')

    if not retired_users_csv:
        FAIL(ERR_NO_CSV_FILE, 'No users CSV file passed in.')

    LOG('Starting Segment user deletion using config file "{}" and users file "{}"'.format(
        config_file, retired_users_csv
    ))

    config = CONFIG_OR_EXIT(config_file)

    segment_base_url = config['base_urls']['segment']
    auth_token = config['segment_auth_token']
    workplace_slug = config['segment_workspace_slug']

    segment_api = SegmentApi(segment_base_url, auth_token, workplace_slug)

    # Read the CSV file. Log the number of user rows read.
    with open(retired_users_csv, 'r') as csv_file:
        users_reader = csv.reader(csv_file)
        users_rows = list(users_reader)
        LOG("Read {} user rows from CSV file '{}'.".format(len(users_rows), retired_users_csv))

    users_to_delete = []
    for user_info in users_rows:
        users_to_delete.append(
            {
                'retirement_id': user_info[0],
                'id': user_info[1],
                'original_username': user_info[2],
                'ecommerce_segment_id': user_info[3]
            }
        )
    LOG('Attempting Segment deletion of {} users...'.format(len(users_to_delete)))
    if not dry_run:
        try:
            segment_api.delete_and_suppress_learners(users_to_delete, chunk_size)
        except Exception as exc:  # pylint: disable=broad-except
            FAIL_EXCEPTION(ERR_DELETING_USERS, 'Unexpected error occurred!', exc)


if __name__ == '__main__':
    # pylint: disable=unexpected-keyword-arg, no-value-for-parameter
    bulk_delete_segment_users(auto_envvar_prefix='RETIREMENT')
