#! /usr/bin/env python3
"""
Command-line script to delete GDPR partner reports on Google Drive that were created over N days ago.
"""

from datetime import datetime, timedelta
from functools import partial
from os import path
import io
import json
import logging
import sys

import click
import yaml
from pytz import UTC

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.google_api import DriveApi  # pylint: disable=wrong-import-position
from tubular.scripts.helpers import _log, _fail, _fail_exception  # pylint: disable=wrong-import-position
from tubular.scripts.retirement_partner_report import REPORTING_FILENAME_PREFIX  # pylint: disable=wrong-import-position

SCRIPT_SHORTNAME = 'delete_expired_reports'
LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)
FAIL_EXCEPTION = partial(_fail_exception, SCRIPT_SHORTNAME)

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

# Return codes for various fail cases
ERR_NO_CONFIG = -1
ERR_BAD_CONFIG = -2
ERR_NO_SECRETS = -3
ERR_BAD_SECRETS = -4
ERR_DELETING_REPORTS = -5
ERR_BAD_AGE = -6


def _config_or_exit(config_file, google_secrets_file):
    """
    Returns the config values from the given file, allows overriding of passed in values.
    """
    try:
        with io.open(config_file, 'r') as config:
            config = yaml.safe_load(config)

        # Check required value
        if 'drive_partners_folder' not in config or not config['drive_partners_folder']:
            FAIL(ERR_BAD_CONFIG, 'No drive_partners_folder in config, or it is empty!')

    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_BAD_CONFIG, 'Failed to read config file {}'.format(config_file), exc)

    try:
        # Just load and parse the file to make sure it's legit JSON before doing
        # all of the work to delete old reports.
        with open(google_secrets_file, 'r') as secrets_f:
            json.load(secrets_f)

        config['google_secrets_file'] = google_secrets_file
        return config
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_BAD_SECRETS, 'Failed to read secrets file {}'.format(google_secrets_file), exc)


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
    '--age_in_days',
    type=int,
    help='Days ago from the current time - before which all GDPR partner reports will be deleted.'
)
def delete_expired_reports(config_file, google_secrets_file, age_in_days):
    """
    Performs the partner report deletion as needed.
    """
    LOG('Starting partner report deletion using config file "{}", Google config "{}", and {} days back'.format(
        config_file, google_secrets_file, age_in_days
    ))

    if not config_file:
        FAIL(ERR_NO_CONFIG, 'No config file passed in.')

    if not google_secrets_file:
        FAIL(ERR_NO_SECRETS, 'No secrets file passed in.')

    if age_in_days <= 0:
        FAIL(ERR_BAD_AGE, 'age_in_days must be a positive integer.')

    config = _config_or_exit(config_file, google_secrets_file)

    try:
        delete_before_dt = datetime.now(UTC) - timedelta(days=age_in_days)
        drive = DriveApi(config['google_secrets_file'])
        LOG('DriveApi configured')
        drive.delete_files_older_than(
            config['drive_partners_folder'],
            delete_before_dt,
            mimetype='text/csv',
            prefix="{}_{}".format(REPORTING_FILENAME_PREFIX, config['partner_report_platform_name'])
        )
        LOG('Partner report deletion complete')
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_DELETING_REPORTS, 'Unexpected error occurred!', exc)


if __name__ == '__main__':
    # pylint: disable=unexpected-keyword-arg, no-value-for-parameter
    delete_expired_reports(auto_envvar_prefix='RETIREMENT')
