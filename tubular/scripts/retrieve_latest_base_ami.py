#! /usr/bin/env python3

"""
Command-line script used to retrieve the last base AMI ID used for an environment/deployment/play.
"""
# pylint: disable=invalid-name


import io
import logging
import re
import sys
import traceback
from os import path

import click
import requests
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular import ec2  # pylint: disable=wrong-import-position

logging.basicConfig(level=logging.INFO)


@click.command()
@click.option(
    '--environment', '-e',
    help='Environment for AMI, e.g. prod, stage',
    required=True,
)
@click.option(
    '--deployment', '-d',
    help='Deployment for AMI e.g. edx, edge',
    required=True,
)
@click.option(
    '--play', '-p',
    help='Play for AMI, e.g. edxapp, insights, discovery',
    required=True,
)
@click.option(
    '--override',
    help='Override AMI id to use',
)
@click.option(
    '--ubuntu_version',
    help='Override AMI id to use',
)
@click.option(
    '--region',
    help='AWS region for the AMI',
    default="us-east-1",
)
@click.option(
    '--out_file',
    help='Output file for the AMI information yaml.',
    default=None,
)
def retrieve_latest_base_ami(environment, deployment, play, override, ubuntu_version, out_file, region):
    """
    Method used to retrieve the latest AMI ID from Ubuntu cloud images locator.
    Also adds tags from latest app ami for the pr messenger and wiki page writer to diff releases
    """

    try:
        edp_ami_id = ec2.active_ami_for_edp(environment, deployment, play)
        if override:
            ami_id = override
        else:
            url = ""
            click.secho('Ubuntu version :  {}'.format(ubuntu_version), fg='green')
            if ubuntu_version == "16.04":
                url = "https://cloud-images.ubuntu.com/query/xenial/server/released.current.txt"
                click.secho('Xenial.\n: {}'.format(url), fg='green')
            elif ubuntu_version == "18.04":
                url = "https://cloud-images.ubuntu.com/query/bionic/server/released.current.txt"
                click.secho('Bionic.\n: {}'.format(url), fg='green')
            if url == "":
                url = "https://cloud-images.ubuntu.com/query/xenial/server/released.current.txt"
            data = requests.get(url)
            parse_ami = re.findall('ebs-ssd(.+?)amd64(.+?){}(.+?)hvm'.format(region), data.content.decode('utf-8'))
            ami_id = parse_ami[0][2].strip()
            click.secho('AMI ID fetched from Ubuntu Cloud : {}'.format(ami_id), fg='red')

        ami_info = {
            # This is passed directly to an ansible script that expects a base_ami_id variable
            'base_ami_id': ami_id,
            # This matches the key produced by the create_ami.yml ansible play to make
            # generating release pages easier.
            'ami_id': ami_id,
        }
        ami_info.update(ec2.tags_for_ami(edp_ami_id))
        logging.info("Found latest AMI ID : {ami_id}".format(
            ami_id=ami_id
        ))

        if out_file:
            with io.open(out_file, 'w') as stream:
                yaml.safe_dump(ami_info, stream, default_flow_style=False, explicit_start=True)
        else:
            print(yaml.safe_dump(ami_info, default_flow_style=False, explicit_start=True))

    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho('Error finding base AMI ID.\nMessage: {}'.format(err), fg='red')
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    retrieve_latest_base_ami()  # pylint: disable=no-value-for-parameter
