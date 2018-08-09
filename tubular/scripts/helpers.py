"""
Common helper methods to use in tubular scripts.
"""
import io
import json
import sys
import traceback
import unicodedata
from os import path

import click
import yaml
from six import text_type

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.edx_api import CredentialsApi, EcommerceApi, LmsApi  # pylint: disable=wrong-import-position


def _log(kind, message):
    """
    Convenience method to log text. Prepended "kind" text makes finding log entries easier.
    """
    click.echo('{}: {}'.format(kind, message))


def _fail(kind, code, message):
    """
    Convenience method to fail out of the command with a message and traceback.
    """
    _log(kind, message)

    # Try to get a traceback, if there is one. On Python 3.4 this raises an AttributeError
    # if there is no current exception, so we eat that here.
    try:
        _log(kind, traceback.format_exc())
    except AttributeError:
        pass

    exit(code)


def _fail_exception(kind, code, message, exc):
    """
    A version of fail that takes an exception to be utf-8 decoded
    """
    exc_msg = text_type(exc)

    # Slumber inconveniently discards the decoded .text attribute from the Response object, and
    # instead gives us the raw encoded .content attribute, so we need to decode it first. Using
    # hasattr here instead of try/except to keep our original exception intact.
    if hasattr(exc, 'content'):
        exc_msg += '\n' + exc.content.decode('utf-8')

    message += '\n' + exc_msg
    _fail(kind, code, message)


def _config_or_exit(fail_func, fail_code, config_file):
    """
    Returns the config values from the given file, allows overriding of passed in values.
    """
    try:
        with io.open(config_file, 'r') as config:
            config = yaml.load(config)

        return config
    except Exception as exc:  # pylint: disable=broad-except
        fail_func(fail_code, 'Failed to read config file {}'.format(config_file), exc)


def _config_with_drive_or_exit(fail_func, config_fail_code, google_fail_code, config_file, google_secrets_file):
    """
    Returns the config values from the given file, allows overriding of passed in values.
    """
    try:
        with io.open(config_file, 'r') as config:
            config = yaml.load(config)

        # Check required values
        for var in ('org_partner_mapping', 'drive_partners_folder'):
            if var not in config or not config[var]:
                fail_func(config_fail_code, 'No {} in config, or it is empty!'.format(var), ValueError())

        # Force the partner names into NFKC here and when we get the folders to ensure
        # they are using the same characters. Otherwise accented characters will not match.
        for org in config['org_partner_mapping']:
            partner = config['org_partner_mapping'][org]
            config['org_partner_mapping'][org] = unicodedata.normalize('NFKC', text_type(partner))
    except Exception as exc:  # pylint: disable=broad-except
        fail_func(config_fail_code, 'Failed to read config file {}'.format(config_file), exc)

    try:
        # Just load and parse the file to make sure it's legit JSON before doing
        # all of the work to get the users.
        with open(google_secrets_file, 'r') as secrets_f:
            json.load(secrets_f)

        config['google_secrets_file'] = google_secrets_file
        return config
    except Exception as exc:  # pylint: disable=broad-except
        fail_func(google_fail_code, 'Failed to read secrets file {}'.format(google_secrets_file), exc)


def _setup_lms_api_or_exit(fail_func, fail_code, config):
    """
    Performs setup of EdxRestClientApi for LMS and returns the validated, sorted list of users to report on.
    """
    try:
        lms_base_url = config['base_urls']['lms']
        client_id = config['client_id']
        client_secret = config['client_secret']

        config['LMS'] = LmsApi(lms_base_url, lms_base_url, client_id, client_secret)
    except Exception as exc:  # pylint: disable=broad-except
        fail_func(fail_code, text_type(exc))


def _setup_all_apis_or_exit(fail_func, fail_code, config):
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
                fail_func(fail_code, 'Service URL is not configured, but required for state {}'.format(state))

        config['LMS'] = LmsApi(lms_base_url, lms_base_url, client_id, client_secret)

        if ecommerce_base_url:
            config['ECOMMERCE'] = EcommerceApi(lms_base_url, ecommerce_base_url, client_id, client_secret)

        if credentials_base_url:
            config['CREDENTIALS'] = CredentialsApi(lms_base_url, credentials_base_url, client_id, client_secret)
    except Exception as exc:  # pylint: disable=broad-except
        fail_func(fail_code, 'Unexpected error occurred!', exc)
