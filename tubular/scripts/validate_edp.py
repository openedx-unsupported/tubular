#! /usr/bin/env python3

"""
Command-line script to validate that an AMI was built for a particular EDP.
"""

import logging
import sys
import traceback
from os import path

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.ec2 import validate_edp  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


@click.command()
@click.option(
    '--ami_id', '-a',
    envvar='AMI_ID',
    help='The ami-id to deploy',
    required=True
)
@click.option(
    '--environment', '-e',
    envvar='AMI_ENVIRONMENT',
    help='Environment for AMI, e.g. prod, stage',
    required=True
)
@click.option(
    '--deployment', '-d',
    envvar='AMI_DEPLOYMENT',
    help='Deployment for AMI e.g. edx, edge',
    required=True
)
@click.option(
    '--play', '-p',
    envvar='AMI_PLAY',
    help='Play for AMI, e.g. edxapp, insights, discovery',
    required=True
)
def validate_cli(ami_id, environment, deployment, play):
    """
    Method to validate that an AMI was built for a particular EDP.
    """
    ami_id = ami_id.strip()
    try:
        edp_matched = validate_edp(ami_id, environment, deployment, play)
    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho("Error validating AMI: {0}.\nMessage: {1}".format(ami_id, err), fg='red')
        sys.exit(1)

    sys.exit(0 if edp_matched else 1)


if __name__ == "__main__":
    validate_cli()  # pylint: disable=no-value-for-parameter
