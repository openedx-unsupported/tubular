#! /usr/bin/env python3

"""
Command-line script to build a frontend application.
"""
from __future__ import absolute_import
from __future__ import unicode_literals

import io
import json
import subprocess
import sys
from datetime import datetime
from functools import partial
from os import path

import click
import yaml
from git import Repo

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.git_repo import LocalGitAPI  # pylint: disable=wrong-import-position
from tubular.scripts.helpers import _log, _fail  # pylint: disable=wrong-import-position

SCRIPT_SHORTNAME = 'Build frontend'
LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)


@click.command()
@click.option(
    '--env-config-file',
    help='File from which to read the environment configuration variables.',
)
@click.option(
    '--app-name',
    help='Name of the frontend app.',
)
@click.option(
    '--version-file',
    help='File to which to write app version info to.',
)
def frontend_build(env_config_file, app_name, version_file):
    """
    Builds a frontend application.

    Uses the provided environment-specific configuration file to pass
    environment variables to the frontend build.

    Args:
        env_config_file (str): Path to a YAML file containing environment configuration variables.
        app_name (str): Name of the frontend app.
        version_file (str): Path to a file to which application version info will be written.
    """
    if not env_config_file:
        FAIL(1, 'Environment config file was not specified.')
    if not app_name:
        FAIL(1, 'App name was not specified.')
    if not version_file:
        FAIL(1, 'Version file was not specified.')

    try:
        with io.open(env_config_file, 'r') as contents:
            env_vars = yaml.safe_load(contents)
    except IOError:
        FAIL(1, 'Environment config file could not be opened.')

    app_config = env_vars.get('APP_CONFIG', {})
    if not app_config:
        LOG('Config variables do not exist for app {}.'.format(app_name))

    proc = subprocess.Popen(['npm install'], cwd=app_name, shell=True)
    return_code = proc.wait()
    if return_code != 0:
        FAIL(return_code, 'Could not run `npm install` for app {}.'.format(app_name))

    env_vars = ['{}={}'.format(k, v) for k, v in app_config.items()]
    proc = subprocess.Popen(
        ' '.join(env_vars + ['npm run build']),
        cwd=app_name,
        shell=True
    )
    return_code = proc.wait()
    if return_code != 0:
        FAIL(return_code, 'Could not run `npm run build` for app {}.'.format(app_name))

    # Add version.json file to build.
    version = {
        'repo': app_name,
        'commit': LocalGitAPI(Repo(app_name)).get_head_sha(),
        'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    try:
        with io.open(version_file, 'w') as output_file:
            json.dump(version, output_file)
    except IOError:
        FAIL(1, 'Could not write to version file for app {}.'.format(app_name))

    LOG(
        'Frontend app {} built successfully with config file {}.'.format(
            app_name,
            env_config_file,
        )
    )


if __name__ == "__main__":
    frontend_build()  # pylint: disable=no-value-for-parameter
