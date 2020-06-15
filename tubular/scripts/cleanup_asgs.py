#! /usr/bin/env python3

"""
Command-line script used to delete AWS Auto-Scaling Groups that are tagged for deletion via Asgard.
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
from tubular.ec2 import get_asgs_pending_delete  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


@click.command()
def delete_asg():
    """
    Method to delete AWS Auto-Scaling Groups via Asgard that are tagged for deletion.
    """
    error = False
    try:
        click.echo("Getting ASGs to delete")
        asgs = get_asgs_pending_delete()
        click.echo("Got ASGs to delete")
        for asg in asgs:
            click.echo("Attempting to delete ASG {0}".format(asg.name))
            try:
                asgard.delete_asg(asg.name, wait_for_deletion=False)
                click.secho("Successfully deleted ASG {0}".format(asg.name), fg='green')
            except Exception as e:  # pylint: disable=broad-except
                click.secho("Unable to delete ASG: {0} - {1}".format(asg, e), fg='red')
                error = True
    except Exception as e:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho("An error occured while cleaning up ASGs: {0}".format(e), fg='red')
        error = True

    if error:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    delete_asg()
