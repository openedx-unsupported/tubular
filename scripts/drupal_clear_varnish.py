#! /usr/bin/env python3

"""
Command-line script to clear the Varnish cache for an environment.
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
@click.option("--env", help="The environment to clear varnish caches in.", type=str, required=True)
@click.option("--username", help="The Acquia username necessary to run the command.", type=str, required=True)
@click.option("--password", help="The Acquia password necessary to run the command.", type=str, required=True)
def clear_varnish_cache(env, username, password):
    """
    Clears the Varnish cache from a Drupal domain.

    Args:
        env (str): The environment to clear varnish caches in (e.g. test or prod)
        username (str): The Acquia username necessary to run the command.
        password (str): The Acquia password necessary to run the command.
    """
    drupal.clear_varnish_cache(env, username, password)

if __name__ == "__main__":
    clear_varnish_cache()  # pylint: disable=no-value-for-parameter
