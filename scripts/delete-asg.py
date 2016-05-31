#!/usr/bin/env python
import sys
import logging
import traceback
import click
from os import path

# Add top-level module path to sys.path before importing tubular code.
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )

from tubular import asgard


logging.basicConfig(stream=sys.stdout, level=logging.INFO)

@click.command()
@click.option('--asg_name', envvar='ASG_NAME', help='the name of the Autoscale Group to delete', required=True)
def delete_asg(asg_name):
    try:
        asgard.delete_asg(asg_name, True)
    except Exception as e:
        traceback.print_exc()
        click.secho("Error Deleting ASG: {0}.\nMessage: {1}".format(asg_name, e.message), fg='red')
        sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    delete_asg()
