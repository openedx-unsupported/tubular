#! /usr/bin/env python3
"""
Command-line script to drive the user retirement workflow for a single user
"""
from __future__ import absolute_import, unicode_literals

from time import time
from os import path
import io
import logging
import sys
import traceback

import click
import yaml
from slumber.exceptions import HttpNotFoundError

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.edx_api import CredentialsApi, EcommerceApi, LmsApi  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
LOG = logging.getLogger(__name__)

# "Magic" states with special meaning, these are required to be in LMS
START_STATE = 'PENDING'
ERROR_STATE = 'ERRORED'
COMPLETE_STATE = 'COMPLETE'
ABORTED_STATE = 'ABORTED'
END_STATES = (ERROR_STATE, ABORTED_STATE, COMPLETE_STATE)

# The retirement process definition. Tuple is (start state, end state, service, api path)
WORKING_STATE_ORDER = [
    # These do not exist yet, though the plumbing for them in edx_api should all be there.
    # ('RETIRING_CREDENTIALS', 'CREDENTIALS_COMPLETE', 'CREDENTIALS', 'retire_learner'),
    # ('RETIRING_ECOM', 'ECOM_COMPLETE', 'ECOMMERCE', 'retire_learner'),
    ('RETIRING_FORUMS', 'FORUMS_COMPLETE', 'LMS', 'retirement_retire_forum'),
    ('RETIRING_EMAIL_LISTS', 'EMAIL_LISTS_COMPLETE', 'LMS', 'retirement_retire_mailings'),
    ('RETIRING_ENROLLMENTS', 'ENROLLMENTS_COMPLETE', 'LMS', 'retirement_unenroll'),
    ('RETIRING_LMS', 'LMS_COMPLETE', 'LMS', 'retirement_lms_retire'),
]

# List of states where an API call is currently in progress
WORKING_STATES = [state[0] for state in WORKING_STATE_ORDER]

# The full list of all of our states
ALL_STATES = [START_STATE]
for working in WORKING_STATE_ORDER:
    ALL_STATES.append(working[0])
    ALL_STATES.append(working[1])
for end in END_STATES:
    ALL_STATES.append(end)

# Tells us when to stop iterating over working states
LAST_WORKING_END_STATE_INDEX = ALL_STATES.index(END_STATES[0]) - 1

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


def _log(info):
    """
    Convenience method to log text. We're currently not sending these to, ex, Splunk, but the
    prepended text would make finding these entries easier if we go that route.
    """
    click.echo('Learner Retirement: {}'.format(info))


def _fail(code, message):
    """
    Convenience method to fail out of the command with a message and traceback.
    """
    _log(message)

    # Try to get a traceback, if there is one. On Python 3.4 this raises an AttributeError
    # if there is no current exception, so we eat that here.
    try:
        _log(traceback.format_exc())
    except AttributeError:
        pass

    exit(code)


def _config_or_fail(config_file):
    """
    Returns the config values from the given file, allows overriding of passed in values.
    """
    try:
        with io.open(config_file, 'r') as config:
            config_yaml = yaml.load(config)

        return (
            config_yaml['client_id'],
            config_yaml['client_secret'],
            config_yaml['base_urls']['lms'],
            # These two are optional
            config_yaml['base_urls'].get('ecommerce', None),
            config_yaml['base_urls'].get('credentials', None)
        )
    except Exception as exc:  # pylint: disable=broad-except
        _fail(ERR_BAD_CONFIG, 'Failed to read config file {} with error: {}'.format(config_file, str(exc)))


def _get_learner_state_index_or_fail(learner):
    """
    Returns the index in the ALL_STATES retirement state list, validating that it is in
    an appropriate state to work on.
    """
    try:
        learner_state = learner['current_state']['state_name']
        learner_state_index = ALL_STATES.index(learner_state)

        if learner_state in END_STATES:
            _fail(ERR_USER_AT_END_STATE, 'User already in end state: {}'.format(learner_state))

        if learner_state in WORKING_STATES:
            _fail(ERR_USER_IN_WORKING_STATE, 'User is already in a working state! {}'.format(learner_state))

        return learner_state_index
    except KeyError:
        _fail(ERR_BAD_LEARNER, 'Bad learner response missing current_state or state_name: {}'.format(learner))
    except ValueError:
        _fail(ERR_UNKNOWN_STATE, 'Unknown learner retirement state for learner: {}'.format(learner))


def _setup_or_fail(username, client_id, client_secret, lms_base_url, ecommerce_base_url, credentials_base_url):
    """
    Performs setup of EdxRestClientApi instances for LMS, E-Commerce, and Credentials,
    as well as fetching the learner's record from LMS and validating that it is in a
    state to work on. Returns the learner dict and their current stage in the
    retirement flow.
    """
    try:
        for state in WORKING_STATE_ORDER:
            if (state[2] == 'ECOMMERCE' and ecommerce_base_url is None) or \
                    (state[2] == 'CREDENTIALS' and credentials_base_url is None):
                _fail(ERR_SETUP_FAILED, 'Service URL is not configured, but required for state {}'.format(state))

        APIS['LMS'] = LmsApi(lms_base_url, lms_base_url, client_id, client_secret)

        if ecommerce_base_url:
            APIS['ECOMMERCE'] = EcommerceApi(lms_base_url, ecommerce_base_url, client_id, client_secret)

        if credentials_base_url:
            APIS['CREDENTIALS'] = CredentialsApi(lms_base_url, credentials_base_url, client_id, client_secret)

        try:
            learner = APIS['LMS'].get_learner_retirement_state(username)
            learner_state_index = _get_learner_state_index_or_fail(learner)
            return learner, learner_state_index
        except HttpNotFoundError:
            _fail(ERR_BAD_LEARNER, 'Learner {} not found. Please check that the learner is present in '
                                   'UserRetirementStatus, is not already retired, '
                                   'and is in an appropriate state to be acted upon.'.format(username))
    except Exception as exc:  # pylint: disable=broad-except
        _fail(ERR_SETUP_FAILED, str(exc))


@click.command()
@click.option(
    '--username',
    help='The original username of the user to retire'
)
@click.option(
    '--config_file',
    help='File in which YAML config exists that overrides all other params.'
)
@click.option(
    '--client_id',
    help='ID of OAuth client used in svr-to-svr client credentials grant.'
)
@click.option(
    '--client_secret',
    help='Secret associated with OAuth client used in svr-to-svr client credentials grant.'
)
@click.option(
    '--lms_base_url',
    help='Base URL of LMS from which to retrieve learner list, including :<port> if non-standard.',
    default='http://localhost'
)
@click.option(
    '--ecommerce_base_url',
    help='Base URL of E-Commerce service, including :<port> if non-standard.',
    default='http://localhost'
)
@click.option(
    '--credentials_base_url',
    help='Base URL of Credentials service, including :<port> if non-standard.',
    default='http://localhost'
)
def retire_learner(
        username,
        config_file,
        client_id,
        client_secret,
        lms_base_url,
        ecommerce_base_url,
        credentials_base_url
):
    """
    Retrieves a JWT token as the retirement service learner, then performs the retirement process as
    defined in WORKING_STATE_ORDER
    """
    _log('Starting learner retiremenet for {}'.format(username))

    if config_file:
        _log('Using config file')
        client_id, client_secret, lms_base_url, ecommerce_base_url, credentials_base_url = _config_or_fail(config_file)

    learner, learner_state_index = _setup_or_fail(
        username,
        client_id,
        client_secret,
        lms_base_url,
        ecommerce_base_url,
        credentials_base_url
    )

    start_state = None
    response = None
    try:
        for start_state, end_state, service, method in WORKING_STATE_ORDER:
            response = None

            # Skip anything that has already been done
            if ALL_STATES.index(start_state) < learner_state_index:
                _log('State {} completed in previous run, skipping'.format(start_state))
                continue

            _log('Starting state {}'.format(start_state))

            APIS['LMS'].update_learner_retirement_state(username, start_state, 'Starting: {}'.format(start_state))

            # This does the actual API call
            start_time = time()
            response = getattr(APIS[service], method)(learner)
            end_time = time()

            _log('State {} completed in {} seconds'.format(start_state, end_time - start_time))

            APIS['LMS'].update_learner_retirement_state(
                username,
                end_state,
                'Ending: {} with response:\n{}'.format(end_state, response)
            )

            learner_state_index += 1

            _log('Progressing to state {}'.format(end_state))

            if learner_state_index > LAST_WORKING_END_STATE_INDEX:
                APIS['LMS'].update_learner_retirement_state(username, COMPLETE_STATE, 'Learner retirement complete.')
                break

        _log('Retirement complete for learner {}'.format(username))
    except Exception as exc:  # pylint: disable=broad-except
        exc_msg = str(exc)

        try:
            exc_msg += '\n' + str(exc.content)
        except AttributeError:
            pass

        try:
            _log('Error in retirement state {}: {}'.format(start_state, exc_msg))
            APIS['LMS'].update_learner_retirement_state(username, ERROR_STATE, exc_msg)
        except Exception as update_exc:  # pylint: disable=broad-except
            _log('Critical error attempting to change learner state to ERRORED: {}'.format(update_exc))

        _fail(ERR_WHILE_RETIRING, 'Error encountered in {}: {}'.format(start_state, exc_msg))


if __name__ == '__main__':
    # pylint: disable=unexpected-keyword-arg, no-value-for-parameter
    retire_learner(auto_envvar_prefix='RETIREMENT')
