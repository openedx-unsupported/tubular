#! /usr/bin/env python3

"""
Command-line script used to delete AWS EC2 instances that have been leftover from incomplete gocd runs
"""

import logging
import sys
import traceback

import click

from tubular import ec2

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command()
@click.option(
    '--region',
    help='aws region',
    default='us-east-1',
    type=str
)
@click.option(
    '--max_run_hours',
    help='Number of hours instance should be left running before termination',
    default=24,
    type=int
)
@click.option(
    '--skip_if_tag',
    default='do_not_delete',
    help='If this tag exists, do not terminate the instance',
    type=str,
)
@click.option(
    '--key_name_filter',
    default='gocd automation run*',
    help='String used to filter the key pair name of instances to terminate',
    type=str,
)
def terminate_instances(region,
                        max_run_hours,
                        skip_if_tag,
                        key_name_filter):
    """
    Delete AWS EC2 instances that have been leftover from incomplete gocd runs

    Args:
        region (str):
        max_run_hours (int):
        skip_if_tag (str):
        key_name_filter (str):

    """
    try:
        terminated_instances = ec2.terminate_instances(region,
                                                       {'key-name': key_name_filter}, max_run_hours, skip_if_tag)
        logging.info("terminated instances: {}".format(terminated_instances))
    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho('Error finding base AMI ID.\nMessage: {}'.format(err), fg='red')
        sys.exit(1)


if __name__ == "__main__":
    terminate_instances()  # pylint: disable=no-value-for-parameter
