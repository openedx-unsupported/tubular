#! /usr/bin/env python3

"""
Command-line script used to deploy an AMI.
"""
# pylint: disable=invalid-name

import io
import logging
import os
import sys
import time
import traceback

import click
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tubular import asgard  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command()
@click.option(
    '--ami_id',
    help='The AMI id to deploy.'
)
@click.option(
    '--config-file',
    help='The config file from which to to get the AMI id.'
)
@click.option(
    '--out_file',
    help='output file for the deploy information yaml',
    default=None
)
@click.option(
    '--dry-run',
    envvar='DRY_RUN',
    help='Don\'t actually deploy.',
    is_flag=True,
    default=False
)
def deploy(ami_id, config_file, out_file, dry_run):
    """
    Deploys the specified AMI from either 'ami_id' or 'config-file'.
    """
    if ami_id is not None and config_file is not None:
        LOG.error('Must specify either --ami_id or --config-file, but not both.')
        sys.exit(1)

    if ami_id is None and config_file is None:
        LOG.error('Must specify at least one of --ami_id or --config-file.')
        sys.exit(1)

    if config_file:
        config = yaml.safe_load(io.open(config_file, 'r'))
        if config and 'ami_id' in config:
            ami_id = config['ami_id']
        else:
            LOG.error('No ami_id found in config file \'{}\'.'.format(config_file))
            sys.exit(1)

    ami_id = ami_id.strip()
    try:
        if not dry_run:
            deploy_info = asgard.deploy(ami_id)
        else:
            click.echo('DRY RUN: Would have triggered a deploy of AMI \'{}\'.'.format(ami_id))
            deploy_info = {}

        # Record the time of deployment in epoch seconds.
        deploy_info['deploy_time'] = time.time()

        if out_file:
            with io.open(out_file, 'w') as stream:
                yaml.safe_dump(deploy_info, stream, default_flow_style=False, explicit_start=True)
        else:
            print(yaml.safe_dump(deploy_info, default_flow_style=False, explicit_start=True))

    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        LOG.error('Error Deploying AMI: {0}.\nMessage: {1}'.format(ami_id, err))
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    deploy()  # pylint: disable=no-value-for-parameter
