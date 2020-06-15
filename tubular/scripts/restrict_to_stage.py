#! /usr/bin/env python3

"""
Command-line script to allow only AMI deployments to stage - and no other environments.
"""

import logging
import sys
import traceback
from os import path

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.ec2 import is_stage_ami  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


@click.command()
@click.option('--ami_id', '-a', envvar='AMI_ID', help='The ami-id to deploy', required=True)
def restrict_ami_to_stage(ami_id):
    """
    Method to allow only AMI deployments to stage - and no other environments.
    """
    ami_id = ami_id.strip()
    try:
        is_stage = is_stage_ami(ami_id)
    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho("Error restricting AMI to stage: {0}.\nMessage: {1}".format(ami_id, err), fg='red')
        sys.exit(1)

    sys.exit(0 if is_stage else 1)


if __name__ == "__main__":
    restrict_ami_to_stage()  # pylint: disable=no-value-for-parameter
