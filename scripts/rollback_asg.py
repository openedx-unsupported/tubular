#!/usr/bin/env python
import sys
import logging
import traceback
import click
import yaml
from os import path

# Add top-level module path to sys.path before importing tubular code.
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )

from tubular import asgard


logging.basicConfig(stream=sys.stdout, level=logging.INFO)


@click.command()
@click.option('--out_file', help='output file for the deploy information yaml', default=None)
@click.option('--config-file', envvar='CONFIG_FILE', help='The config file to to get the ami_id from.')
@click.option('--dry-run', envvar='DRY_RUN', help='Don\'t actually deploy.', is_flag=True, default=False)
def rollback(config_file, dry_run):
    """
    Roll back to an existing ASG. If the desired ASG(s) are not available to roll back (have since been deleted)
    and an AMI_ID is specified a new ASG using that AMI ID will be used.

    Configuration file input:
    ---
    current_asgs:
      loadtest-edx-edxapp:
        - loadtest-edx-edxapp-v099
      loadtest-edx-worker:
        - loadtest-edx-worker-v099
    disabled_asgs:
      loadtest-edx-edxapp:
        - loadtest-edx-edxapp-v058
        - loadtest-edx-edxapp-v059
      loadtest-edx-worker:
        - loadtest-edx-worker-v034

    The disabled_asgs will be enabled and the current_asgs will be disabled.

    Args:
        config_file:
        dry_run:

    Returns:

    """
    config = yaml.safe_load(open(config_file, 'r'))


    try:
        if not dry_run:
            deploy_info = asgard.deploy(ami_id)
        else:
            click.echo('Would have triggered a deploy of {}'.format(ami_id))
            deploy_info = {}

        if out_file:
            with open(out_file, 'w') as stream:
                yaml.safe_dump(deploy_info, stream, default_flow_style=False, explicit_start=True)
        else:
            print yaml.dump(deploy_info, default_flow_style=False, explicit_start=True)

    except Exception as e:
        traceback.print_exc()
        click.secho('Error Deploying AMI: {0}.\nMessage: {1}'.format(ami_id, e.message), fg='red')
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    rollback()
