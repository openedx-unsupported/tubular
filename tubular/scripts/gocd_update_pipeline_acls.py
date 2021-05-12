#! /usr/bin/env python3

"""
Command-line script used to update acls of the pipeline groups of all the gocd pipelines
to use the appropriate onelogin groups
"""

import sys
import logging
import traceback
import re
import click
import requests
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tubular.gocd_api import (  # pylint: disable=wrong-import-position
    list_pipeline_group_configs,
    update_pipeline_group_config,
    get_pipeline_group_config,
)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)

@click.command()
@click.option('--host', help='gocd hostname without protocol eg gocd.tools.edx.org', required=True)
@click.option('--token', help='gocd auth token', required=True)
def update_pipeline_acls(token, host):
    """
    For the specified profile get the pod yaml and replace the tag of any images that
    match with the new tag for a given profile
    """
    try:
        logging.info("Updating pipeline ACLs...")
        list_response = list_pipeline_group_configs(host, token).json()
        pipeline_groups = list_response['_embedded']['groups']
        # Everything should be set to this ACL, it grants devs the ability to see and execute all pipelines
        # and SRE the ability to administer them
        desired_authorization = {'view': {'users': [], 'roles': ['sre', 'developers']}, 'operate': {'users': [], 'roles': ['sre', 'developers']}, 'admins': {'users': [], 'roles': ['sre']}}
        for group in pipeline_groups:
            name = group['name']
            authorization = group['authorization']
            if authorization != desired_authorization:
                logging.info(f"Attempting to update pipeline group config for pipeline group: {name}")
                # Handle needs update case
                fresh_group_response = get_pipeline_group_config(host, token, name)
                etag = fresh_group_response.headers['etag']
                fresh_group = fresh_group_response.json()
                fresh_group['authorization'] = desired_authorization
                update_pipeline_group_config(host, token, etag, name, fresh_group)

    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho('{}'.format(err), fg='red')
        sys.exit(1)

if __name__ == "__main__":
    update_pipeline_acls()  # pylint: disable=no-value-for-parameter