#! /usr/bin/env python3
"""
Command-line script to drive the partner reporting part of the retirement process
"""
from __future__ import absolute_import, unicode_literals

from collections import defaultdict, OrderedDict
from datetime import date
import csv
import json
import io
import logging
import os
import sys
import traceback
import unicodedata

import click
import yaml
from six import PY2, text_type

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tubular.edx_api import LmsApi  # pylint: disable=wrong-import-position
from tubular.google_api import DriveApi  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
LOG = logging.getLogger(__name__)

# We'll store the access token here once retrieved
AUTH_HEADER = {}

# Return codes for various fail cases
ERR_SETUP_FAILED = -1
ERR_FETCHING_LEARNERS = -2
ERR_NO_CONFIG = -3
ERR_NO_SECRETS = -4
ERR_NO_OUTPUT_DIR = -5
ERR_BAD_CONFIG = -6
ERR_BAD_SECRETS = -7
ERR_UNKNOWN_ORG = -8
ERR_REPORTING = -9
ERR_DRIVE_UPLOAD = -10
ERR_CLEANUP = -11
ERR_DRIVE_LISTING = -12

# This text will be the comment body for all new CSV uploads.
NOTIFICATION_MESSAGE = 'Your learner retirement report from edX has been published to Drive.'


class PartnerDoesNotExist(Exception):
    """
    A custom exception to catch the case where a learner has a partner lists that doesn't exist
    in the configuration.
    """
    pass


def _log(info):
    """
    Convenience method to log text.  The prepended text would make finding
    these entries easier in logging aggratation services.
    """
    click.echo('Partner report: {}'.format(info))


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


def _fail_exception(code, exc, message):
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
    _fail(code, message)


def _config_or_exit(config_file, google_secrets_file):
    """
    Returns the config values from the given file, allows overriding of passed in values.
    """
    try:
        with io.open(config_file, 'r') as config:
            config = yaml.load(config)

        # Check required values
        for var in ('org_partner_mapping', 'drive_partners_folder'):
            if var not in config or not config[var]:
                _fail(ERR_BAD_CONFIG, 'No {} in config, or it is empty!'.format(var))

        # Force the partner names into NFKC here and when we get the folders to ensure
        # they are using the same characters. Otherwise accented characters will not match.
        for org in config['org_partner_mapping']:
            partner = config['org_partner_mapping'][org]
            if PY2:
                partner = partner.decode('utf-8')
            config['org_partner_mapping'][org] = unicodedata.normalize('NFKC', partner)
    except Exception as exc:  # pylint: disable=broad-except
        _fail_exception(ERR_BAD_CONFIG, exc, 'Failed to read config file {}'.format(config_file))

    try:
        # Just load and parse the file to make sure it's legit JSON before doing
        # all of the work to get the users.
        with open(google_secrets_file, 'r') as secrets_f:
            json.load(secrets_f)

        config['google_secrets_file'] = google_secrets_file
        return config
    except Exception as exc:  # pylint: disable=broad-except
        _fail_exception(ERR_BAD_SECRETS, exc, 'Failed to read secrets file {}'.format(google_secrets_file))


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
        _fail(ERR_SETUP_FAILED, text_type(exc))


def _get_orgs_and_learners_or_exit(config):
    """
    Contacts LMS to get the list of learners to report on and the orgs they belong to.
    Reformats them into dicts with keys of the orgs and lists of learners as the value
    and returns a tuple of that dict plus a list of all of the learner usernames.
    """
    try:
        learners = config['lms_api'].retirement_partner_report()
        orgs = defaultdict(list)
        usernames = []

        # Organize the learners, create separate dicts per partner, make sure partner is in the mapping.
        # learners can appear in more than one dict.
        for learner in learners:
            usernames.append(learner['original_username'])
            for org in learner['orgs']:
                try:
                    reporting_org = config['org_partner_mapping'][org]
                except KeyError:
                    raise PartnerDoesNotExist(org)

                orgs[reporting_org].append(learner)
        return orgs, usernames
    except PartnerDoesNotExist as exc:
        _fail(ERR_UNKNOWN_ORG, 'Partner for organization "{}" does not exist in configuration.'.format(text_type(exc)))
    except Exception as exc:  # pylint: disable=broad-except
        _fail(ERR_FETCHING_LEARNERS, text_type(exc))


def _generate_report_files_or_exit(report_data, output_dir):
    """
    Spins through the partners, creating a single CSV file for each
    """
    # We'll store all of the partner to file links here so we can be sure all files generated successfully
    # before trying to push to Google, minimizing the cases where we might have to overwrite files
    # already up there.
    partner_filenames = {}

    for partner in report_data:
        _log('Starting report for partner {}: {} learners to add'.format(partner, len(report_data[partner])))

        try:
            # Fields for each learner to write, in order these are also the header names
            fields = ['original_username', 'original_email', 'original_name']
            outfile = os.path.join(output_dir, '{}_{}.csv'.format(partner, date.today().isoformat()))

            # If there is already a file for this date, assume it is bad and replace it
            try:
                os.remove(outfile)
            except OSError:
                pass

            with open(outfile, 'w') as f:
                writer = csv.DictWriter(f, fields, dialect=csv.excel, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(report_data[partner])

            partner_filenames[partner] = outfile
            _log('Report complete for partner {}'.format(partner))
        except Exception as exc:  # pylint: disable=broad-except
            _fail_exception(ERR_REPORTING, exc, 'Error reporting retirement for partner {}'.format(partner))

    return partner_filenames


def _config_drive_folder_map_or_exit(config):
    """
    Lists folders under our top level parent for this environment and returns
    a dict of {partner name: folder id}. Partner names should match the values
    in config['org_partner_mapping']
    """
    drive = DriveApi(config['google_secrets_file'])

    try:
        folders = drive.list_subfolders(config['drive_partners_folder'])
    except Exception as exc:  # pylint: disable=broad-except
        _fail_exception(ERR_DRIVE_LISTING, exc, 'Finding partner directories on Drive failed.')

    # As in _config_or_exit we force normalize the unicode here to make sure the keys
    # match. Otherwise the name we get back from Google won't match what's in the YAML config.
    config['partner_folder_mapping'] = OrderedDict()
    for folder in folders:
        if PY2:
            folder['name'] = folder['name'].decode('utf-8')
        folder['name'] = unicodedata.normalize('NFKC', folder['name'])
        config['partner_folder_mapping'][folder['name']] = folder['id']


def _push_files_to_google(config, partner_filenames):
    """
    Copy the file to Google drive for this partner

    Returns:
        List of file IDs for the uploaded csv files.
    """
    # First make sure we have Drive folders for all partners
    failed_partners = []
    for partner in partner_filenames:
        if partner not in config['partner_folder_mapping']:
            failed_partners.append(partner)

    if failed_partners:
        _fail(ERR_BAD_CONFIG, 'These partners have retiring learners, but no Drive folder: {}'.format(failed_partners))

    file_ids = []
    drive = DriveApi(config['google_secrets_file'])
    for partner in partner_filenames:
        # This is populated on the fly in _config_drive_folder_map_or_exit
        folder_id = config['partner_folder_mapping'][partner]
        file_id = None
        with open(partner_filenames[partner], 'rb') as f:
            try:
                _log('Attempting to upload {} to {} Drive folder.'.format(partner_filenames[partner], partner))
                file_id = drive.create_file_in_folder(folder_id, partner_filenames[partner], f, "text/csv")
            except Exception as exc:  # pylint: disable=broad-except
                _fail_exception(ERR_DRIVE_UPLOAD, exc, 'Drive upload failed for: {}'.format(partner_filenames[partner]))
        file_ids.append(file_id)
    return file_ids


def _add_comments_to_files(config, file_ids):
    """
    Add comments to the uploaded csv files, triggering email notification.

    Args:
        file_ids (list of str): Drive file IDs corresponding to the list of newly uploaded csv files.
    """
    drive = DriveApi(config['google_secrets_file'])
    try:
        _log('Attempting to add notification comments to uploaded csv files.')
        drive.create_comments_for_files(file_ids, NOTIFICATION_MESSAGE)
    except Exception as exc:  # pylint: disable=broad-except
        # do not fail the script here, since comment errors are non-critical
        _log('WARNING: there was an error adding Google Drive comments to the csv files: {}'.format(exc))


@click.command()
@click.option(
    '--config_file',
    help='YAML file that contains retirement related configuration for this environment.'
)
@click.option(
    '--google_secrets_file',
    help='JSON file with Google service account credentials for uploading.'
)
@click.option(
    '--output_dir',
    help='The local directory that the script will write the reports to.'
)
@click.option(
    '--comments/--no_comments',
    default=True,
    help='Do or skip adding notification comments to the reports.'
)
def generate_report(config_file, google_secrets_file, output_dir, comments):
    """
    Retrieves a JWT token as the retirement service learner, then performs the reporting process as that user.

    - Accepts the configuration file with all necessary credentials and URLs for a single environment
    - Gets the users in the LMS reporting queue and the partners they need to be reported to
    - Generates a single report per partner
    - Pushes the reports to Google Drive
    - On success tells LMS to remove the users who succeeded from the reporting queue
    """
    _log('Starting partner report using config file {} and Google config {}'.format(config_file, google_secrets_file))

    try:
        if not config_file:
            _fail(ERR_NO_CONFIG, 'No config file passed in.')

        if not google_secrets_file:
            _fail(ERR_NO_SECRETS, 'No secrets file passed in.')

        # The Jenkins DSL is supposed to create this path for us
        if not output_dir or not os.path.exists(output_dir):
            _fail(ERR_NO_OUTPUT_DIR, 'No output_dir passed in or path does not exist.')

        config = _config_or_exit(config_file, google_secrets_file)
        _setup_lms_or_exit(config)
        _config_drive_folder_map_or_exit(config)
        report_data, all_usernames = _get_orgs_and_learners_or_exit(config)
        partner_filenames = _generate_report_files_or_exit(report_data, output_dir)

        # All files generated successfully, now push them to Google
        report_file_ids = _push_files_to_google(config, partner_filenames)

        if comments:
            # All files uploaded successfully, now add comments to them to trigger notifications
            _add_comments_to_files(config, report_file_ids)

        # Success, tell LMS to remove these users from the queue
        config['lms_api'].retirement_partner_cleanup(all_usernames)
        _log('All reports completed and uploaded to Google.')
    except Exception as exc:  # pylint: disable=broad-except
        _fail_exception(ERR_CLEANUP, exc, 'Unexpected error occurred! Users may be stuck in the processing state!')


if __name__ == '__main__':
    # pylint: disable=unexpected-keyword-arg, no-value-for-parameter
    generate_report(auto_envvar_prefix='RETIREMENT')
