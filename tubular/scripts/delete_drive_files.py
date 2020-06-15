#! /usr/bin/env python3
"""
Command-line script to delete Google Drive files by ID.
"""

import logging
import sys
from functools import partial
from os import path

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.google_api import DriveApi  # pylint: disable=wrong-import-position
# pylint: disable=wrong-import-position
from tubular.scripts.helpers import (
    _config_with_drive_or_exit,
    _fail,
    _fail_exception,
    _log
)

# The Google API cannot delete more than this number of file IDs at once.
MAX_FILE_IDS = 100

# Return codes for various fail cases
ERR_NO_CONFIG = -1
ERR_BAD_CONFIG = -2
ERR_NO_SECRETS = -3
ERR_BAD_SECRETS = -4
ERR_DELETING_FILES = -5
ERR_NO_FILE_IDS = -6
ERR_TOO_MANY_FILE_IDS = -7

SCRIPT_SHORTNAME = 'delete_drive_files'
LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)
FAIL_EXCEPTION = partial(_fail_exception, SCRIPT_SHORTNAME)
CONFIG_WITH_DRIVE_OR_EXIT = partial(_config_with_drive_or_exit, FAIL_EXCEPTION, ERR_BAD_CONFIG, ERR_BAD_SECRETS)

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


@click.command()
@click.option(
    '--config_file',
    help='YAML file that contains retirement-related configuration for this environment.'
)
@click.option(
    '--google_secrets_file',
    help='JSON file with Google service account credentials for deletion purposes.'
)
@click.option(
    '--file_id',
    multiple=True,
    help='File ID(s) of Google Drive file(s) to delete.'
)
def delete_files(config_file, google_secrets_file, file_id):
    """
    Deletes the specified Google Drive files by ID.
    """
    LOG('Starting Drive file deletion using config file "{}" and Google config "{}"'.format(
        config_file, google_secrets_file
    ))

    # The file_id option collects *all* file_id options from the command-line.
    # So there's likely multiple file IDs to process. Rename this option for clarity.
    file_ids = file_id

    if not config_file:
        FAIL(ERR_NO_CONFIG, 'No config file passed in.')

    if not google_secrets_file:
        FAIL(ERR_NO_SECRETS, 'No secrets file passed in.')

    if not file_ids:
        FAIL(ERR_NO_FILE_IDS, 'No file IDs were specified.')

    if len(file_ids) > MAX_FILE_IDS:
        FAIL(ERR_TOO_MANY_FILE_IDS, "Too many file IDs specfied: {}. Maximum is {}".format(len(file_ids), MAX_FILE_IDS))

    config = CONFIG_WITH_DRIVE_OR_EXIT(config_file, google_secrets_file)

    try:
        drive = DriveApi(config['google_secrets_file'])
        drive.delete_files(file_ids)
        LOG('All files deleted successfully.')
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_DELETING_FILES, 'Unexpected error occurred!', exc)


if __name__ == '__main__':
    # pylint: disable=unexpected-keyword-arg, no-value-for-parameter
    delete_files(auto_envvar_prefix='RETIREMENT')
