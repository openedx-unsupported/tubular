"""
Command-line script used to deploy an AMI.
"""
# pylint: disable=invalid-name,open-builtin
from __future__ import unicode_literals

from os import path
import os
import sys
import logging
import time
import traceback
import click
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular import asgard  # pylint: disable=wrong-import-position


logging.basicConfig(stream=sys.stdout, level=logging.INFO)


@click.command()
@click.option('--ami_id', envvar='AMI_ID', help='The ami-id to deploy')
@click.option('--out_file', help='output file for the deploy information yaml', default=None)
@click.option('--config-file', envvar='CONFIG_FILE', help='The config file to to get the ami_id from.')
@click.option('--dry-run', envvar='DRY_RUN', help='Don\'t actually deploy.', is_flag=True, default=False)
def deploy(ami_id, out_file, config_file, dry_run):
    """
    Method which deploys an AMI.
    """
    env_ami_id = os.environ.get('AMI_ID', None)
    if env_ami_id and ami_id != env_ami_id:
        click.secho(
            'Error: Command-line and env var AMI_ID do not match. ({} != {})'.format(ami_id, env_ami_id),
            fg='red'
        )
        sys.exit(1)

    if config_file:
        config = yaml.safe_load(open(config_file, 'r'))
        if config:
            if not ami_id and 'ami_id' in config:
                ami_id = config['ami_id']
    if not ami_id:
        click.secho('AMI ID not specified in environment, on cli or in config file.', fg='red')
        sys.exit(1)

    ami_id = ami_id.strip()
    try:
        if not dry_run:
            deploy_info = asgard.deploy(ami_id)
        else:
            click.echo('Would have triggered a deploy of {}'.format(ami_id))
            deploy_info = {}

        # Record the time of deployment in epoch seconds.
        deploy_info['deploy_time'] = time.time()

        if out_file:
            with open(out_file, 'w') as stream:
                yaml.safe_dump(deploy_info, stream, default_flow_style=False, explicit_start=True)
        else:
            print yaml.safe_dump(deploy_info, default_flow_style=False, explicit_start=True)

    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho('Error Deploying AMI: {0}.\nMessage: {1}'.format(ami_id, err.message), fg='red')
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    deploy()  # pylint: disable=no-value-for-parameter
