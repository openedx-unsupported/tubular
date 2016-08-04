#!/usr/bin/env python
import sys
from os import path
import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )

from tubular import drupal


@click.command()
@click.option("--env", help="The environment the database backup will take place in.", type=str, required=True)
@click.option("--username", help="The Acquia username necessary to run the command.", type=str, required=True)
@click.option("--password", help="The Acquia password necessary to run the command.", type=str, required=True)
def backup_database(env, username, password):
    """
    Creates a backup of the database in the specified environment.

    Args:
        env (str): The environment the database backup will take place in (e.g. test or prod)
        username (str): The Acquia username necessary to run the command.
        password (str): The Acquia password necessary to run the command.
    """
    drupal.backup_database(env, username, password)

if __name__ == "__main__":
    backup_database()
