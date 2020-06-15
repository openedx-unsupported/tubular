#! /usr/bin/env python3

"""
Command-line script to check if a migration's duration exceeded a certain
migration duration threshold.
"""

import io
import logging
import os
import sys

import click
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tubular.tubular_email import send_email  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command()
@click.option(
    '--migration_file',
    required=True,
    help='File containing YAML output from which to read migration duration details.'
)
@click.option(
    '--duration_threshold',
    type=int,
    required=True,
    help='Threshold in seconds - if total migration time exceeds it, an email alert is sent.'
)
@click.option(
    '--instance_data',
    required=True,
    help='String used to identify this particular run of the pipeline to send in an alert.'
)
@click.option(
    '--fail_upon_alert',
    is_flag=True,
    help='When set and duration threshold is exceeded, exit as failed.'
)
@click.option(
    '--from_address',
    required=True,
    help='Email address which the email will be From:'
)
@click.option(
    '--alert_email',
    multiple=True,
    help='Email address to alert when migration threshold is exceeded. Multiple emails can be specified.'
)
@click.option(
    '--aws_ses_region',
    default='us-east-1',
    help='AWS region whose SES instance will be used to send email.'
)
def check_migrate_duration(migration_file,
                           duration_threshold,
                           instance_data,
                           fail_upon_alert,
                           from_address,
                           alert_email,
                           aws_ses_region):
    """
    Check if a migration's duration exceeded a certain migration duration threshold.
    If so, email an alert to the specified email addresses.
    """
    migration_info = yaml.safe_load(io.open(migration_file, 'r'))[0]
    duration = migration_info['duration']
    threshold_exceeded = (duration >= duration_threshold)
    if threshold_exceeded:
        info_msg = "Migration duration ({duration} sec) exceeded threshold ({threshold} sec).".format(
            duration=duration,
            threshold=duration_threshold
        )
        subject = "ALERT: {}".format(info_msg)
        body = "Migration instance: {}\n\nMigration output:\n{}\n".format(
            instance_data,
            migration_info['output']
        )
        send_email(aws_ses_region, from_address, alert_email, subject, body)

    sys.exit(int(fail_upon_alert and threshold_exceeded))


if __name__ == "__main__":
    check_migrate_duration()  # pylint: disable=no-value-for-parameter
