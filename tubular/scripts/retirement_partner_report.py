#! /usr/bin/env python3
# coding=utf-8

"""
Command-line script to drive the partner reporting part of the retirement process
"""
# NOTE: Make sure that all non-ascii text written to standard output (including
# print statements and logging) is manually encoded to bytes using a utf-8 or
# other encoding.  We currently make use of this script within a context that
# does NOT tolerate unicode text on sys.stdout, namely python 2 on Build
# Jenkins.  PLAT-2287 tracks this Tech Debt.

from __future__ import absolute_import, unicode_literals

from collections import defaultdict, OrderedDict
from datetime import date
from functools import partial
import logging
import os
import sys
import unicodedata
import unicodecsv as csv

import click
from six import text_type

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tubular.google_api import DriveApi  # pylint: disable=wrong-import-position
# pylint: disable=wrong-import-position
from tubular.scripts.helpers import (
    _config_with_drive_or_exit,
    _fail,
    _fail_exception,
    _log,
    _setup_lms_api_or_exit
)


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

SCRIPT_SHORTNAME = 'Partner report'
LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)
FAIL_EXCEPTION = partial(_fail_exception, SCRIPT_SHORTNAME)
CONFIG_WITH_DRIVE_OR_EXIT = partial(_config_with_drive_or_exit, FAIL_EXCEPTION, ERR_BAD_CONFIG, ERR_BAD_SECRETS)
SETUP_LMS_OR_EXIT = partial(_setup_lms_api_or_exit, FAIL, ERR_SETUP_FAILED)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Prefix which starts all generated report filenames.
REPORTING_FILENAME_PREFIX = 'user_retirement'

# We'll store the access token here once retrieved
AUTH_HEADER = {}

# This text template will be the comment body for all new CSV uploads.  The
# following format variables need to be provided:
#   tags: space delimited list of google user tags, e.g. "+user1@gmail.com +user2@gmail.com"
NOTIFICATION_MESSAGE_TEMPLATE = """
Hello from edX. Dear {tags}, a new report listing the learners enrolled in your institution’s courses on edx.org that have requested deletion of their edX account and associated personal data within the last week has been published to Google Drive. Please access your folder to see the latest report. If you have any questions, please contact your edX Project Coordinator.
""".strip()


def _check_all_learner_orgs_or_exit(config, learners):
    """
    Checks all leaners and their orgs, ensuring that each org has a mapping to a partner Drive folder.
    If any orgs are missing a mapping, fails after printing the mismatched orgs.
    """
    # Loop through all learner orgs, checking for their mappings.
    mismatched_orgs = set()
    for learner in learners:
        for org in learner['orgs']:
            if org not in config['org_partner_mapping']:
                mismatched_orgs.add(org)
    if mismatched_orgs:
        FAIL(
            ERR_UNKNOWN_ORG,
            'Partners for organizations {} do not exist in configuration.'.format(text_type(mismatched_orgs))
        )


def _get_orgs_and_learners_or_exit(config):
    """
    Contacts LMS to get the list of learners to report on and the orgs they belong to.
    Reformats them into dicts with keys of the orgs and lists of learners as the value
    and returns a tuple of that dict plus a list of all of the learner usernames.
    """
    try:
        learners = config['LMS'].retirement_partner_report()

        _check_all_learner_orgs_or_exit(config, learners)

        orgs = defaultdict(list)
        usernames = []

        # Organize the learners, create separate dicts per partner, make sure partner is in the mapping.
        # learners can appear in more than one dict.
        for learner in learners:
            usernames.append({'original_username': learner['original_username']})

            # Use the datetime upon which the record was 'created' in the partner reporting queue
            # as the approximate time upon which user retirement was completed ('deletion_completed')
            # for the record's user.
            learner['deletion_completed'] = learner['created']

            for org in learner['orgs']:
                reporting_org = config['org_partner_mapping'][org]
                orgs[reporting_org].append(learner)

        return orgs, usernames
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_FETCHING_LEARNERS, 'Unexpected exception occurred!', exc)


def _generate_report_files_or_exit(config, report_data, output_dir):
    """
    Spins through the partners, creating a single CSV file for each
    """
    # We'll store all of the partner to file links here so we can be sure all files generated successfully
    # before trying to push to Google, minimizing the cases where we might have to overwrite files
    # already up there.
    partner_filenames = {}

    for partner in report_data:
        LOG('Starting report for partner {}: {} learners to add'.format(partner, len(report_data[partner])))

        try:
            # Fields for each learner to write, in order these are also the header names
            fields = ['user_id', 'original_username', 'original_email', 'original_name', 'deletion_completed']
            outfile = os.path.join(output_dir, '{}_{}_{}_{}.csv'.format(
                REPORTING_FILENAME_PREFIX, config['partner_report_platform_name'], partner, date.today().isoformat()
            ))

            # If there is already a file for this date, assume it is bad and replace it
            try:
                os.remove(outfile)
            except OSError:
                pass

            with open(outfile, 'wb') as f:
                writer = csv.DictWriter(f, fields, dialect=csv.excel, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(report_data[partner])

            partner_filenames[partner] = outfile
            LOG('Report complete for partner {}'.format(partner))
        except Exception as exc:  # pylint: disable=broad-except
            FAIL_EXCEPTION(ERR_REPORTING, 'Error reporting retirement for partner {}'.format(partner), exc)

    return partner_filenames


def _config_drive_folder_map_or_exit(config):
    """
    Lists folders under our top level parent for this environment and returns
    a dict of {partner name: folder id}. Partner names should match the values
    in config['org_partner_mapping']
    """
    drive = DriveApi(config['google_secrets_file'])

    try:
        folders = drive.walk_files(
            config['drive_partners_folder'],
            mimetype='application/vnd.google-apps.folder',
            recurse=False
        )
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_DRIVE_LISTING, 'Finding partner directories on Drive failed.', exc)

    # As in _config_or_exit we force normalize the unicode here to make sure the keys
    # match. Otherwise the name we get back from Google won't match what's in the YAML config.
    config['partner_folder_mapping'] = OrderedDict()
    for folder in folders:
        folder['name'] = unicodedata.normalize('NFKC', text_type(folder['name']))
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
        FAIL(ERR_BAD_CONFIG, 'These partners have retiring learners, but no Drive folder: {}'.format(failed_partners))

    file_ids = {}
    drive = DriveApi(config['google_secrets_file'])
    for partner in partner_filenames:
        # This is populated on the fly in _config_drive_folder_map_or_exit
        folder_id = config['partner_folder_mapping'][partner]
        file_id = None
        with open(partner_filenames[partner], 'rb') as f:
            try:
                drive_filename = os.path.basename(partner_filenames[partner])
                LOG('Attempting to upload {} to {} Drive folder.'.format(drive_filename, partner))
                file_id = drive.create_file_in_folder(folder_id, drive_filename, f, "text/csv")
            except Exception as exc:  # pylint: disable=broad-except
                FAIL_EXCEPTION(ERR_DRIVE_UPLOAD, 'Drive upload failed for: {}'.format(drive_filename), exc)
        file_ids[partner] = file_id
    return file_ids


def _add_comments_to_files(config, file_ids):
    """
    Add comments to the uploaded csv files, triggering email notification.

    Args:
        file_ids (dict): Mapping of partner names to Drive file IDs corresponding to the newly uploaded csv files.
    """
    drive = DriveApi(config['google_secrets_file'])

    partner_folders_to_permissions = drive.list_permissions_for_files(
        config['partner_folder_mapping'].values(),
        fields='emailAddress',
    )

    # create a mapping of partners to a list of permissions dicts:
    permissions = {
        partner: partner_folders_to_permissions[config['partner_folder_mapping'][partner]]
        for partner in file_ids
    }

    # throw out all edx.org addresses, and flatten the permissions dicts to just the email:
    external_emails = {
        partner: [
            perm['emailAddress']
            for perm in permissions[partner]
            if not perm['emailAddress'].lower().endswith('@edx.org')
        ]
        for partner in permissions
    }

    file_ids_and_comments = []
    for partner in file_ids:
        tag_string = ' '.join('+' + email for email in external_emails[partner])
        comment_content = NOTIFICATION_MESSAGE_TEMPLATE.format(tags=tag_string)
        file_ids_and_comments.append((file_ids[partner], comment_content))

    try:
        LOG('Adding notification comments to uploaded csv files.')
        drive.create_comments_for_files(file_ids_and_comments)
    except Exception as exc:  # pylint: disable=broad-except
        # do not fail the script here, since comment errors are non-critical
        LOG('WARNING: there was an error adding Google Drive comments to the csv files: {}'.format(exc))


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
    LOG('Starting partner report using config file {} and Google config {}'.format(config_file, google_secrets_file))

    try:
        if not config_file:
            FAIL(ERR_NO_CONFIG, 'No config file passed in.')

        if not google_secrets_file:
            FAIL(ERR_NO_SECRETS, 'No secrets file passed in.')

        # The Jenkins DSL is supposed to create this path for us
        if not output_dir or not os.path.exists(output_dir):
            FAIL(ERR_NO_OUTPUT_DIR, 'No output_dir passed in or path does not exist.')

        config = CONFIG_WITH_DRIVE_OR_EXIT(config_file, google_secrets_file)
        SETUP_LMS_OR_EXIT(config)
        _config_drive_folder_map_or_exit(config)
        report_data, all_usernames = _get_orgs_and_learners_or_exit(config)
        partner_filenames = _generate_report_files_or_exit(config, report_data, output_dir)

        # All files generated successfully, now push them to Google
        report_file_ids = _push_files_to_google(config, partner_filenames)

        if comments:
            # All files uploaded successfully, now add comments to them to trigger notifications
            _add_comments_to_files(config, report_file_ids)

        # Success, tell LMS to remove these users from the queue
        config['LMS'].retirement_partner_cleanup(all_usernames)
        LOG('All reports completed and uploaded to Google.')
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_CLEANUP, 'Unexpected error occurred! Users may be stuck in the processing state!', exc)


if __name__ == '__main__':
    # pylint: disable=unexpected-keyword-arg, no-value-for-parameter
    generate_report(auto_envvar_prefix='RETIREMENT')
