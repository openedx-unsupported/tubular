#! /usr/bin/env python3

"""
Command-line script to fetch a deployed Drupal tag.
"""

import sys
from os import path

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular import drupal  # pylint: disable=wrong-import-position


@click.command()
@click.option("--app_id", help="The application id for drupal instance.", type=str, required=True)
@click.option("--env", help="The environment to fetch the current tag name in.", type=str, required=True)
@click.option("--client_id", help="The Acquia api client id necessary to run the command.", type=str, required=True)
@click.option("--secret", help="The Acquia api secret key to run the command.", type=str, required=True)
@click.option("--path_name", help="The path to write the tag name to", type=str, required=True)
def fetch_deployed_tag(app_id, env, client_id, secret, path_name):
    """
    Fetches the currently deployed tag in the given environment

    Args:
        app_id (str): The application id for drupal instance.
        env (str): The environment to fetch the current tag name in (e.g. test or prod)
        client_id (str): The Acquia api client id necessary to run the command.
        secret (str): The Acquia api secret key to run the command.
        path_name (str): The path to write the tag name to.
    """
    drupal.fetch_deployed_tag(app_id, env, client_id, secret, path_name)


if __name__ == "__main__":
    fetch_deployed_tag()  # pylint: disable=no-value-for-parameter
