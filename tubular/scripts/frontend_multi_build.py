#! /usr/bin/env python3

"""
Command-line script to build a frontend application.
"""
from __future__ import absolute_import
from __future__ import unicode_literals

import os
import sys
from functools import partial

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tubular.scripts.helpers import _log, _fail  # pylint: disable=wrong-import-position
from tubular.scripts.frontend_utils import FrontendBuilder  # pylint: disable=wrong-import-position

SCRIPT_SHORTNAME = 'Build frontend'
LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)
MULTISITE_PATH = './multisite/dist'


@click.command()
@click.option(
    '--common-config-file',
    help='File from which common configuration variables are read.',
)
@click.option(
    '--env-config-file',
    help='File from which environment configuration variables are read.',
)
@click.option(
    '--app-name',
    help='Name of the frontend app.',
)
@click.option(
    '--version-file',
    help='File to which to write app version info to.',
)
def frontend_build(common_config_file, env_config_file, app_name, version_file):
    """
    Builds a frontend application.

    Uses the provided common and environment-specific configuration files to pass
    environment variables to the frontend build.

    Args:
        common_config_file (str): Path to a YAML file containing common configuration variables.
        env_config_file (str): Path to a YAML file containing environment configuration variables.
        app_name (str): Name of the frontend app.
        version_file (str): Path to a file to which application version info will be written.
    """
    if not app_name:
        FAIL(1, 'App name was not specified.')
    if not version_file:
        FAIL(1, 'Version file was not specified.')
    if not common_config_file:
        FAIL(1, 'Common config file was not specified.')
    if not env_config_file:
        FAIL(1, 'Environment config file was not specified.')

    builder = FrontendBuilder(common_config_file, env_config_file, app_name, version_file)
    builder.install_requirements()
    app_config = builder.get_app_config()
    env_vars = ['{}={}'.format(k, v) for k, v in app_config.items()]

    # If the MULTISITE key is set, build the app once for each site (by setting
    # a HOSTNAME environment variable and store the each build output in
    # `dist/$HOSTNAME`.
    multisite_sites = builder.env_cfg.get('MULTISITE', [])
    os.makedirs(MULTISITE_PATH)
    for site_obj in multisite_sites:
        hostname = site_obj.get('HOSTNAME')
        if not hostname:
            FAIL(1, 'HOSTNAME is not set for a site in in app {}.'.format(app_name))
        env_vars_with_site = env_vars + [" HOSTNAME={}".format(hostname)]
        builder.build_app(
            env_vars_with_site,
            'Could not run `npm run build` for for site {} in app {}.'.format(hostname, app_name)
        )

        # Move built app from ./dist to a folder named after the site in the temporary
        # multisite directory
        os.renames('./dist', os.path.join(MULTISITE_PATH, hostname))

    # Move the temporary directory down to `./dist` for deployment. The ./dist directory
    # will be non-existant since it was moved after each build.
    os.renames(MULTISITE_PATH, './dist')

    builder.create_version_file()

if __name__ == "__main__":
    frontend_build()  # pylint: disable=no-value-for-parameter
