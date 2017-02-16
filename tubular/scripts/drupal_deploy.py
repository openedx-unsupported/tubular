#! /usr/bin/env python3

"""
Command-line script to deploy a Drupal release.
"""
from __future__ import absolute_import
from __future__ import unicode_literals

import sys
from os import path
import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular import drupal  # pylint: disable=wrong-import-position


@click.command()
@click.option("--env", help="The environment to deploy code in.", type=str, required=True)
@click.option("--username", help="The Acquia username necessary to run the command.", type=str, required=True)
@click.option("--password", help="The Acquia password necessary to run the command.", type=str, required=True)
@click.option("--tag", help="The tag name to be deployed to the environment.", type=str, required=True)
def deploy(env, username, password, tag):
    """
    Deploys a given tag to the specified environment.

    Args:
        env (str): The environment to deploy code in (e.g. test or prod)
        username (str): The Acquia username necessary to run the command.
        password (str): The Acquia password necessary to run the command.
        tag (str): The tag to deploy to the specified environment.
    """
    drupal.deploy(env, username, password, tag)

if __name__ == "__main__":
    deploy()  # pylint: disable=no-value-for-parameter
