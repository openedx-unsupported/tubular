#! /usr/bin/env python3

"""
Command-line script to deploy a Drupal release.
"""

import sys
from os import path

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular import drupal  # pylint: disable=wrong-import-position


@click.command()
@click.option("--app_id", help="The application id for drupal instance.", type=str, required=True)
@click.option("--env", help="The environment to deploy code in.", type=str, required=True)
@click.option("--client_id", help="The Acquia api client id necessary to run the command.", type=str, required=True)
@click.option("--secret", help="The Acquia api secret key to run the command.", type=str, required=True)
@click.option("--branch_or_tag", help="The branch or tag name to be deployed to the environment.",
              type=str, required=True)
def deploy(app_id, env, client_id, secret, branch_or_tag):
    """
    Deploys a given tag to the specified environment.

    Arguments:
        app_id (str): The application id for drupal instance.
        env (str): The environment to deploy code in (e.g. test or prod)
        client_id (str): The Acquia api client id necessary to run the command.
        secret (str): The Acquia api secret key to run the command.
        branch_or_tag (str): The branch or tag to deploy to the specified environment.
    """
    drupal.deploy(app_id, env, client_id, secret, branch_or_tag)


if __name__ == "__main__":
    deploy()  # pylint: disable=no-value-for-parameter
