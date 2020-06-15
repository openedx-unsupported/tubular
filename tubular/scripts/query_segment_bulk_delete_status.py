#! /usr/bin/env python3
"""
Command-line script to check status of a bulk delete users request from Segment.
"""

from functools import partial
from os import path
import logging
import sys

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.segment_api import SegmentApi  # pylint: disable=wrong-import-position
# pylint: disable=wrong-import-position
from tubular.scripts.helpers import (
    _config_or_exit,
    _fail,
    _fail_exception,
    _log
)

DEFAULT_CHUNK_SIZE = 5000

# Return codes for various fail cases
ERR_NO_CONFIG = -1
ERR_BAD_CONFIG = -2
ERR_NO_CSV_FILE = -3
ERR_QUERYING_STATUS = -4

SCRIPT_SHORTNAME = 'query_segment_bulk_delete_status'
LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)
FAIL_EXCEPTION = partial(_fail_exception, SCRIPT_SHORTNAME)
CONFIG_OR_EXIT = partial(_config_or_exit, FAIL_EXCEPTION, ERR_BAD_CONFIG)

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


@click.command()
@click.option(
    '--config_file',
    help='YAML file that contains retirement-related configuration for this environment.'
)
@click.option(
    '--bulk_delete_id',
    help='ID from previously-submitted Segment bulk user delete request.'
)
def query_bulk_delete_id(config_file, bulk_delete_id):
    """
    Query the status of a previously-submitted Segment bulk delete request.
    """
    if not config_file:
        FAIL(ERR_NO_CONFIG, 'No config file passed in.')

    LOG('Querying Segment user bulk deletion status for ID "{}" using config file "{}"'.format(
        bulk_delete_id, config_file
    ))

    config = CONFIG_OR_EXIT(config_file)

    segment_base_url = config['base_urls']['segment']
    auth_token = config['segment_auth_token']
    workplace_slug = config['segment_workspace_slug']

    segment_api = SegmentApi(segment_base_url, auth_token, workplace_slug)

    try:
        segment_api.get_bulk_delete_status(bulk_delete_id)
    except Exception as exc:  # pylint: disable=broad-except
        FAIL_EXCEPTION(ERR_QUERYING_STATUS, 'Unexpected error occurred!', exc)


if __name__ == '__main__':
    # pylint: disable=unexpected-keyword-arg, no-value-for-parameter
    query_bulk_delete_id(auto_envvar_prefix='RETIREMENT')
