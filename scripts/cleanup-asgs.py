#!/usr/bin/env python
import sys
import logging
import traceback
import click
from os import path

# Add top-level module path to sys.path before importing tubular code.
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )

from tubular import asgard
from ec2 import get_asgs_pending_delete


logging.basicConfig(stream=sys.stdout, level=logging.INFO)

@click.command()
def delete_asg():
    error = False
    try:
        asgs = get_asgs_pending_delete()
        for asg in asgs:
            try:
                asgard.delete_asg(asg)
            except Exception, e:
                click.secho("Unable to delete ASG: {0} - {1}".format(asg, e.message), fg='red')
                error = True
    except Exception, e:
        traceback.print_exc()
        click.secho("An error occured while cleaning up ASGs: {0}".format(e.message), fg='red')
        error = True

    if error:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    delete_asg()
