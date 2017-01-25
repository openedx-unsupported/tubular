"""
Command-line script to fetch a deployed Drupal tag.
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
@click.option("--env", help="The environment to fetch the current tag name in.", type=str, required=True)
@click.option("--username", help="The Acquia username necessary to run the command.", type=str, required=True)
@click.option("--password", help="The Acquia password necessary to run the command.", type=str, required=True)
@click.option("--path_name", help="The path to write the tag name to", type=str, required=True)
def fetch_deployed_tag(env, username, password, path_name):
    """
    Fetches the currently deployed tag in the given environment

    Args:
        env (str): The environment to fetch the current tag name in (e.g. test or prod)
        username (str): The Acquia username necessary to run the command.
        password (str): The Acquia password necessary to run the command.
        path_name (str): The path to write the tag name to.
    """
    drupal.fetch_deployed_tag(env, username, password, path_name)

if __name__ == "__main__":
    fetch_deployed_tag()  # pylint: disable=no-value-for-parameter
