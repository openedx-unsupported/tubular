#! /usr/bin/env python3

"""
Command-line script to check an api endpoint.
"""
from __future__ import absolute_import
from __future__ import unicode_literals

import os
import requests
import sys
from functools import partial

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tubular.scripts.helpers import _log, _fail  # pylint: disable=wrong-import-position

SCRIPT_SHORTNAME = 'Check API'
LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)


@click.command()
@click.option(
    '--api-endpoint',
    help='API endpoint to check.',
)
def check_api(api_endpoint):
    """
    Requests an api endpoint and takes action depending on the result

    Args:
        api_endpoint(str): URL of an api endpoint to request.
    """
    if not api_endpoint:
        FAIL(1, 'API endpoint was not specified.')
    result = requests.get(api_endpoint)

    LOG(
         'Requested {url} and received response code: {response_code} and body: {body}.'.format(
             url=api_endpoint,
             response_code=result.status_code,
             body=result.text,
        )
    )

if __name__ == "__main__":
    check_api()  # pylint: disable=no-value-for-parameter
