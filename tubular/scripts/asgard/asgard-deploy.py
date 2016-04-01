#!/usr/bin/env python
import sys
import logging
import click
import tubular.asgard as asgard

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)

@click.command()
@click.option('--ami_id', envvar='AMI_ID', help='The ami-id to deploy', required=True)
def deploy(ami_id):
    try:
        asgard.deploy(ami_id)
    except Exception, e:
        click.secho("Error Deploying AMI: {0}.\nMessage: {1}".format(ami_id, e.message), fg='red')
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    deploy()