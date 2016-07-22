#!/usr/bin/env python
import click
from tubular import drupal


@click.command()
@click.option("--env", help="The environment to clear varnish caches in.", type=str, required=True)
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
    deploy()
