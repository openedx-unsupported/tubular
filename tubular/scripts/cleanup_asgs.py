#! /usr/bin/env python3

"""
Command-line script used to delete AWS Auto-Scaling Groups that are tagged for deletion via Asgard.
"""
# pylint: disable=invalid-name

from os import path
import sys
import logging
import traceback
import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular import asgard  # pylint: disable=wrong-import-position
from tubular.ec2 import get_asgs_pending_delete  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


@click.command("delete_asg")
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
            click.echo(f"Attempting to delete ASG {asg.name}")
            try:
                asgard.delete_asg(asg.name, wait_for_deletion=False)
                click.secho(f"Successfully deleted ASG {asg.name}", fg='green')
            except Exception as e:  # pylint: disable=broad-except
                click.secho(f"Unable to delete ASG: {asg} - {e}", fg='red')
                error = True
    except Exception as e:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho(f"An error occured while cleaning up ASGs: {e}", fg='red')
        error = True

    if error:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    delete_asg()
