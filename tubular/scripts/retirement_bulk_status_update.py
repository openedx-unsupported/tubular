#! /usr/bin/env python3
"""
Command-line script to bulk update retirement states in LMS
"""
from __future__ import absolute_import, unicode_literals

from datetime import datetime
from functools import partial
from os import path
import io
import logging
import sys

import click
import yaml
from six import text_type

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.edx_api import LmsApi  # pylint: disable=wrong-import-position
from tubular.scripts.helpers import _log, _fail, _fail_exception  # pylint: disable=wrong-import-position

SCRIPT_SHORTNAME = 'Bulk Status'
LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)
FAIL_EXCEPTION = partial(_fail_exception, SCRIPT_SHORTNAME)

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

# Return codes for various fail cases
ERR_NO_CONFIG = -1
ERR_BAD_CONFIG = -2
ERR_FETCHING = -3
ERR_UPDATING = -4
ERR_SETUP_FAILED = -5


def _config_or_exit(config_file):
    """
    Returns the config values from the given file, allows overriding of passed in values.
    """
    try:
        with io.open(config_file, 'r') as config:
            config = yaml.load(config)

        return config
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_BAD_CONFIG, 'Failed to read config file {}'.format(config_file), exc)


def _setup_lms_or_exit(config):
    """
    Performs setup of EdxRestClientApi for LMS and returns the validated, sorted list of users to report on.
    """
    try:
        lms_base_url = config['base_urls']['lms']
        client_id = config['client_id']
        client_secret = config['client_secret']

        config['lms_api'] = LmsApi(lms_base_url, lms_base_url, client_id, client_secret)
    except Exception as exc:  # pylint: disable=broad-except
        FAIL(ERR_SETUP_FAILED, text_type(exc))


def validate_dates(_, __, value):
    """
    Click input validator for date options.
    - Validates string format
    - Transforms the string into a datetime.Date object
    - Validates the date is less than or equal to today
    - Returns the Date, or raises a click.BadParameter
    """
    try:
        date = datetime.strptime(value, '%Y-%m-%d').date()
        if date > datetime.now().date():
            raise ValueError()
        return date
    except ValueError:
        raise click.BadParameter('Dates need to be in the format of YYYY-MM-DD and today or earlier.')


def _fetch_learners_to_update_or_exit(config, start_date, end_date, initial_state):
    """
    Makes the call to fetch learners to be bulk updated, returns the list of learners
    or exits.
    """
    LOG('Fetching users in state {} created from {} to {}'.format(initial_state, start_date, end_date))
    try:
        return config['lms_api'].get_learners_by_date_and_status(initial_state, start_date, end_date)
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_FETCHING, 'Unexpected error occurred fetching users to update!', exc)


def _update_learners_or_exit(config, learners, new_state):
    """
    Iterates the list of learners, setting each to the new state. On any error
    it will exit the script.
    """
    LOG('Updating {} learners to {}'.format(len(learners), new_state))
    try:
        for learner in learners:
            config['lms_api'].update_learner_retirement_state(
                learner['original_username'],
                new_state,
                'Force updated via retirement_bulk_status_update Tubular script',
                force=True
            )
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_UPDATING, 'Unexpected error occurred updating users!', exc)


@click.command()
@click.option(
    '--config_file',
    help='YAML file that contains retirement-related configuration for this environment.'
)
@click.option(
    '--initial_state',
    help='Find learners in this retirement state. Use the state name ex: PENDING, COMPLETE'
)
@click.option(
    '--new_state',
    help='Set any found learners to this new state. Use the state name ex: PENDING, COMPLETE'
)
@click.option(
    '--start_date',
    callback=validate_dates,
    help='(YYYY-MM-DD) Earliest creation date for retirements to act on.'
)
@click.option(
    '--end_date',
    callback=validate_dates,
    help='(YYYY-MM-DD) Latest creation date for retirements to act on.'
)
def update_statuses(config_file, initial_state, new_state, start_date, end_date):
    """
    Does the bulk update of statuses
    """
    try:
        LOG('Starting bulk update script: Config: {}'.format(config_file))

        if not config_file:
            FAIL(ERR_NO_CONFIG, 'No config file passed in.')

        config = _config_or_exit(config_file)
        _setup_lms_or_exit(config)

        learners = _fetch_learners_to_update_or_exit(config, start_date, end_date, initial_state)
        _update_learners_or_exit(config, learners, new_state)

        LOG('Bulk update complete')
    except Exception as exc:
        print(text_type(exc))
        raise


if __name__ == '__main__':
    # pylint: disable=unexpected-keyword-arg, no-value-for-parameter
    update_statuses(auto_envvar_prefix='RETIREMENT')
