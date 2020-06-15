#! /usr/bin/env python3

"""
Command-line script used to delete a specified Auto-Scaling Group via Asgard.
"""
# pylint: disable=invalid-name


import logging
import sys
import traceback
from os import path

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular import asgard  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


@click.command()
@click.option('--asg_name', envvar='ASG_NAME', help='the name of the Autoscale Group to delete', required=True)
def delete_asg(asg_name):
    """
    Method to delete a specified Auto-Scaling Group via Asgard.
    """
    asg_name = asg_name.strip()
    try:
        asgard.delete_asg(asg_name, True)
    except Exception as e:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho("Error Deleting ASG: {0}.\nMessage: {1}".format(asg_name, e), fg='red')
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    delete_asg()  # pylint: disable=no-value-for-parameter
