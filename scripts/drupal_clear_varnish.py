#!/usr/bin/env python
import click
from tubular import drupal


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
    clear_varnish_cache()
