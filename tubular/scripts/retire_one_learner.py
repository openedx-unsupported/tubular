#! /usr/bin/env python3
"""
Command-line script to drive the user retirement workflow for a single user

To run this script you will need a username to run against and a YAML config file in the format:

client_id: <client id from LMS DOT>
client_secret: <client secret from LMS DOT>
base_urls:
    lms: http://localhost:18000/
    ecommerce: http://localhost:18130/
    credentials: http://localhost:18150/
retirement_pipeline:
    - ['RETIRING_CREDENTIALS', 'CREDENTIALS_COMPLETE', 'CREDENTIALS', 'retire_learner']
    - ['RETIRING_ECOM', 'ECOM_COMPLETE', 'ECOMMERCE', 'retire_learner']
    - ['RETIRING_FORUMS', 'FORUMS_COMPLETE', 'LMS', 'retirement_retire_forum']
    - ['RETIRING_EMAIL_LISTS', 'EMAIL_LISTS_COMPLETE', 'LMS', 'retirement_retire_mailings']
    - ['RETIRING_ENROLLMENTS', 'ENROLLMENTS_COMPLETE', 'LMS', 'retirement_unenroll']
    - ['RETIRING_LMS', 'LMS_COMPLETE', 'LMS', 'retirement_lms_retire']
"""
from __future__ import absolute_import, unicode_literals

from functools import partial
from os import path
from time import time
import io
import logging
import sys

import click
import yaml
from six import text_type
from slumber.exceptions import HttpNotFoundError

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.edx_api import CredentialsApi, EcommerceApi, LmsApi  # pylint: disable=wrong-import-position
from tubular.scripts.helpers import _log, _fail, _fail_exception  # pylint: disable=wrong-import-position

SCRIPT_SHORTNAME = 'Learner Retirement'
LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)
FAIL_EXCEPTION = partial(_fail_exception, SCRIPT_SHORTNAME)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# "Magic" states with special meaning, these are required to be in LMS
START_STATE = 'PENDING'
ERROR_STATE = 'ERRORED'
COMPLETE_STATE = 'COMPLETE'
ABORTED_STATE = 'ABORTED'
END_STATES = (ERROR_STATE, ABORTED_STATE, COMPLETE_STATE)

# We'll store the access token here once retrieved
AUTH_HEADER = {}

# Holds the edx_rest_api_client API for each service
APIS = {}

# Return codes for various fail cases
ERR_SETUP_FAILED = -1
ERR_USER_AT_END_STATE = -2
ERR_USER_IN_WORKING_STATE = -3
ERR_WHILE_RETIRING = -4
ERR_BAD_LEARNER = -5
ERR_UNKNOWN_STATE = -6
ERR_BAD_CONFIG = -7


def _config_or_fail(config_file):
    """
    Returns the config values from the given file, allows overriding of passed in values.
    """
    try:
        with io.open(config_file, 'r') as config:
            config = yaml.load(config)

        # List of states where an API call is currently in progress
        retirement_pipeline = config['retirement_pipeline']
        config['working_states'] = [state[0] for state in retirement_pipeline]

        # Create the full list of all of our states
        config['all_states'] = [START_STATE]
        for working in config['retirement_pipeline']:
            config['all_states'].append(working[0])
            config['all_states'].append(working[1])
        for end in END_STATES:
            config['all_states'].append(end)

        return config
    except Exception as exc:  # pylint: disable=broad-except
        FAIL(ERR_BAD_CONFIG, 'Failed to read config file {} with error: {}'.format(config_file, text_type(exc)))


def _get_learner_state_index_or_fail(learner, config):
    """
    Returns the index in the ALL_STATES retirement state list, validating that it is in
    an appropriate state to work on.
    """
    try:
        learner_state = learner['current_state']['state_name']
        learner_state_index = config['all_states'].index(learner_state)

        if learner_state in END_STATES:
            FAIL(ERR_USER_AT_END_STATE, 'User already in end state: {}'.format(learner_state))

        if learner_state in config['working_states']:
            FAIL(ERR_USER_IN_WORKING_STATE, 'User is already in a working state! {}'.format(learner_state))

        return learner_state_index
    except KeyError:
        FAIL(ERR_BAD_LEARNER, 'Bad learner response missing current_state or state_name: {}'.format(learner))
    except ValueError:
        FAIL(ERR_UNKNOWN_STATE, 'Unknown learner retirement state for learner: {}'.format(learner))


def _setup_or_fail(username, config):
    """
    Performs setup of EdxRestClientApi instances for LMS, E-Commerce, and Credentials,
    as well as fetching the learner's record from LMS and validating that it is in a
    state to work on. Returns the learner dict and their current stage in the
    retirement flow.
    """
    try:
        lms_base_url = config['base_urls']['lms']
        ecommerce_base_url = config['base_urls']['ecommerce']
        credentials_base_url = config['base_urls']['credentials']
        client_id = config['client_id']
        client_secret = config['client_secret']

        for state in config['retirement_pipeline']:
            if (state[2] == 'ECOMMERCE' and ecommerce_base_url is None) or \
                    (state[2] == 'CREDENTIALS' and credentials_base_url is None):
                FAIL(ERR_SETUP_FAILED, 'Service URL is not configured, but required for state {}'.format(state))

        APIS['LMS'] = LmsApi(lms_base_url, lms_base_url, client_id, client_secret)

        if ecommerce_base_url:
            APIS['ECOMMERCE'] = EcommerceApi(lms_base_url, ecommerce_base_url, client_id, client_secret)

        if credentials_base_url:
            APIS['CREDENTIALS'] = CredentialsApi(lms_base_url, credentials_base_url, client_id, client_secret)

        try:
            learner = APIS['LMS'].get_learner_retirement_state(username)
            learner_state_index = _get_learner_state_index_or_fail(learner, config)
            return learner, learner_state_index
        except HttpNotFoundError:
            FAIL(ERR_BAD_LEARNER, 'Learner {} not found. Please check that the learner is present in '
                                  'UserRetirementStatus, is not already retired, '
                                  'and is in an appropriate state to be acted upon.'.format(username))
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_SETUP_FAILED, 'Unexpected error occurred!', exc)


@click.command()
@click.option(
    '--username',
    help='The original username of the user to retire'
)
@click.option(
    '--config_file',
    help='File in which YAML config exists that overrides all other params.'
)
def retire_learner(
        username,
        config_file
):
    """
    Retrieves a JWT token as the retirement service learner, then performs the retirement process as
    defined in WORKING_STATE_ORDER
    """
    LOG('Starting learner retirement for {} using config file {}'.format(username, config_file))

    if not config_file:
        FAIL(ERR_BAD_CONFIG, 'No config file passed in.')

    config = _config_or_fail(config_file)

    learner, learner_state_index = _setup_or_fail(username, config)

    start_state = None
    response = None
    try:
        for start_state, end_state, service, method in config['retirement_pipeline']:
            response = None

            # Skip anything that has already been done
            if config['all_states'].index(start_state) < learner_state_index:
                LOG('State {} completed in previous run, skipping'.format(start_state))
                continue

            LOG('Starting state {}'.format(start_state))

            APIS['LMS'].update_learner_retirement_state(username, start_state, 'Starting: {}'.format(start_state))

            # This does the actual API call
            start_time = time()
            response = getattr(APIS[service], method)(learner)
            end_time = time()

            LOG('State {} completed in {} seconds'.format(start_state, end_time - start_time))

            APIS['LMS'].update_learner_retirement_state(
                username,
                end_state,
                'Ending: {} with response:\n{}'.format(end_state, response)
            )

            learner_state_index += 1

            LOG('Progressing to state {}'.format(end_state))

        APIS['LMS'].update_learner_retirement_state(username, COMPLETE_STATE, 'Learner retirement complete.')
        LOG('Retirement complete for learner {}'.format(username))
    except Exception as exc:  # pylint: disable=broad-except
        exc_msg = text_type(exc)

        try:
            # Slumber inconveniently discards the decoded .text attribute from the Response object, and instead gives us
            # the raw encoded .content attribute, so we need to decode it first.
            exc_msg += '\n' + exc.content.decode('utf-8')
        except AttributeError:
            pass

        try:
            LOG('Error in retirement state {}: {}'.format(start_state, exc_msg))
            APIS['LMS'].update_learner_retirement_state(username, ERROR_STATE, exc_msg)
        except Exception as update_exc:  # pylint: disable=broad-except
            LOG('Critical error attempting to change learner state to ERRORED: {}'.format(update_exc))

        FAIL_EXCEPTION(ERR_WHILE_RETIRING, 'Error encountered in state "{}"'.format(start_state), exc)


if __name__ == '__main__':
    # pylint: disable=unexpected-keyword-arg, no-value-for-parameter
    retire_learner(auto_envvar_prefix='RETIREMENT')
