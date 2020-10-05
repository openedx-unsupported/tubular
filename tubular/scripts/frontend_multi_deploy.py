#! /usr/bin/env python3

"""
Command-line script to deploy a frontend app to s3.
"""

import sys
from functools import partial
from os import path

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.scripts.frontend_utils import FrontendDeployer  # pylint: disable=wrong-import-position
from tubular.scripts.helpers import _log, _fail  # pylint: disable=wrong-import-position

SCRIPT_SHORTNAME = 'Deploy frontend'
LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)


@click.command()
@click.option(
    '--env-config-file',
    help='File from which to read environment configuration variables.',
)
@click.option(
    '--app-name',
    help='Name of the frontend app.',
)
@click.option(
    '--app-dist',
    help='Path to the frontend app dist directory.',
)
@click.option(
    '--purge-cache',
    default=False,
    is_flag=True,
    help='Boolean to decide if Cloudflare cache needs to be purged or not.',
)
def frontend_deploy(env_config_file, app_name, app_dist, purge_cache):
    """
    Copies a frontend application to an s3 bucket.

    Args:
        env_config_file (str): Path to a YAML file containing environment configuration variables.
        app_name (str): Name of the frontend app.
        app_dist (str): Path to frontend application dist directory.
        purge_cache (bool): Should Cloudflare cache needs to be purged.
    """

    if not env_config_file:
        FAIL(1, 'Environment config file was not specified.')
    if not app_name:
        FAIL(1, 'Frontend application name was not specified.')
    if not app_dist:
        FAIL(1, 'Frontend application dist path was not specified.')

    # We are deploying ALL sites to a single bucket so they live at
    # /<hostname>/ within the global bucket.
    deployer = FrontendDeployer(env_config_file, app_name)
    bucket_name = deployer.env_cfg.get('BUCKET_NAME')
    if not bucket_name:
        FAIL(1, 'No S3 bucket name configured for {}.'.format(app_name))
    deployer.deploy_site(bucket_name, app_dist)
    if purge_cache:
        deployer.purge_cache(bucket_name)


if __name__ == "__main__":
    frontend_deploy()  # pylint: disable=no-value-for-parameter
