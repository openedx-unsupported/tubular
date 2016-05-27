#!/usr/bin/env python
import sys
import logging
import traceback
import click
from os import path

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.ec2 import is_stage_ami

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


@click.command()
@click.option('--ami_id', '-a', envvar='AMI_ID', help='The ami-id to deploy', required=True)
def restrict_ami_to_stage(ami_id):
    try:
        is_stage = is_stage_ami(ami_id)
    except Exception as e:
        traceback.print_exc()
        click.secho("Error restricting AMI to stage: {0}.\nMessage: {1}".format(ami_id, e.message), fg='red')
        sys.exit(1)

    sys.exit(0 if is_stage else 1)

if __name__ == "__main__":
    restrict_ami_to_stage()
