#! /usr/bin/env python3

"""
Command-line script to clear the Varnish cache for an environment.
"""

import sys
from os import path

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular import drupal  # pylint: disable=wrong-import-position


@click.command()
@click.option("--app_id", help="The application id for drupal instance.", type=str, required=True)
@click.option("--env", help="The environment to clear varnish caches in.", type=str, required=True)
@click.option("--client_id", help="The Acquia api client id necessary to run the command.", type=str, required=True)
@click.option("--secret", help="The Acquia password necessary to run the command.", type=str, required=True)
def clear_varnish_cache(app_id, env, client_id, secret):
    """
    Clears the Varnish cache from a Drupal domain.

    Args:
        app_id (str): The application id for drupal instance.
        env (str): The environment to clear varnish caches in (e.g. test or prod)
        client_id (str): The Acquia api client id necessary to run the command.
        secret (str): The Acquia api secret key to run the command.
    """
    drupal.clear_varnish_cache(app_id, env, client_id, secret)


if __name__ == "__main__":
    clear_varnish_cache()  # pylint: disable=no-value-for-parameter
