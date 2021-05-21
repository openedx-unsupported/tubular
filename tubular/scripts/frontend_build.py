#! /usr/bin/env python3

"""
Command-line script to build a frontend application.
"""

import os
import sys
from functools import partial
from typing import Union

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tubular.scripts.helpers import _log, _fail  # pylint: disable=wrong-import-position
from tubular.scripts.frontend_utils import FrontendBuilder  # pylint: disable=wrong-import-position

SCRIPT_SHORTNAME = 'Build frontend'
LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)


@click.command("frontend_build")
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
    env_vars = [
        f"{k}={ensure_wrapped_in_quotes(v)}"
        for k, v in app_config.items()
    ]
    builder.build_app(env_vars, f'Could not run `npm run build` for app {app_name}.')
    builder.create_version_file()
    LOG(f'Frontend app {app_name} built successfully with config file {env_config_file}.')


def ensure_wrapped_in_quotes(value: Union[bool, int, float, str, None]) -> str:
    """
    Given a simple value from YAML, return it wrapped in single quotes, unless it
    is already wrapped in quotes, in which case return it as-is.

    This ensures that strings passed as arguments to npm bash scripts are treated
    as single values, even if they contain spaces. Otherwise, bash would split them
    on the spaces and treat them as a series of individual strings.

    Some frontend configurations already wrap some or all of their values in quotes,
    so for backwards compatibility, we need to avoid wrapping values that are already
    wrapped in single- or double-quotes.

    Examples:
        tomato paste -> 'tomato paste'
        "alfredo sauce" -> "alfredo sauce"
        'aglio e olio' -> 'aglio e olio'
    """
    string_value = str(value)
    if string_value.startswith("'") and string_value.endswith("'"):
        return string_value
    elif string_value.startswith('"') and string_value.endswith('"'):
        return string_value
    else:
        return f"'{string_value}'"

    
if __name__ == "__main__":
    frontend_build()  # pylint: disable=no-value-for-parameter
