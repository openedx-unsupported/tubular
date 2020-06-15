#! /usr/bin/env python3

"""
Command-line script to purge Cloudflare cache by hostname.
"""

import sys
from functools import partial
from os import path

import CloudFlare
import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.scripts.helpers import _log, _fail  # pylint: disable=wrong-import-position

SCRIPT_SHORTNAME = 'Purge Cloudflare cache'
LOG = partial(_log, SCRIPT_SHORTNAME)
FAIL = partial(_fail, SCRIPT_SHORTNAME)


@click.command()
@click.option(
    "--hostname",
    help="Hostname of the app that is being cached",
)
def purge_cloudflare_cache(hostname):
    """
        Purge the Cloudflare cache for the hostname.
        Cloudflare zones are named by domain.
        Assumes the caller's shell has the following environment
        variables set to enable Cloudflare API auth:
        CF_API_EMAIL
        CF_API_KEY
    """
    zone_name = '.'.join(hostname.split('.')[-2:])  # Zone name is the TLD
    data = {'hosts': [hostname]}
    cloudflare_client = CloudFlare.CloudFlare()
    try:
        zone_id = cloudflare_client.zones.get(params={'name': zone_name})[0]['id']  # pylint: disable=no-member
        cloudflare_client.zones.purge_cache.post(zone_id, data=data)  # pylint: disable=no-member
        LOG('Successfully purged Cloudflare cache for hostname {}.'.format(hostname))
    except (CloudFlare.exceptions.CloudFlareAPIError, IndexError, KeyError):
        FAIL(1, 'Failed to purge the Cloudflare cache for hostname {}.'.format(hostname))


if __name__ == "__main__":
    purge_cloudflare_cache()  # pylint: disable=no-value-for-parameter
