#! /usr/bin/env python3

"""
Command-line script used to trigger an update of a previously configured config repo
https://api.gocd.org/current/#trigger-update-of-config-repository
"""

import sys
import logging
import traceback
import re
import click
import requests
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tubular.gocd_api import (  # pylint: disable=wrong-import-position
    trigger_update_config_repository,
    check_if_config_repo_update_completed,
)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)

def is_done_with_update(host, token, config_repo):
    r = check_if_config_repo_update_completed(host, token, config_repo)
    returned_status = r.json['in_progress']
    assert returned_status in [True, False]
    return returned_status

@click.command()
@click.option('--host', help='gocd hostname without protocol eg gocd.tools.edx.org', required=True)
@click.option('--token', help='gocd auth token', required=True)
@click.option('--config_repo', help='config repo name to update', required=True)
@click.option('--timeout', help='Time to wait for config repo to sync', default=60)
def update_config_repo(token, host, config_repo, timeout):
    """
    Trigger a config update 
    """
    try:
        logging.info("Trigger config repo update...")
        trigger_update_config_repository(host, token, config_repo)
        start = time.time()
        while not is_done_with_update:
            logging.info(f"Waiting for update to complete... will timeout after {timeout}s")
            time.sleep(2)
            end = time.time()
            elapsed = end - start
            if elapsed >= timeout:
                logging.error(f"Timed out after {timeout}s")


    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho('{}'.format(err), fg='red')
        sys.exit(1)

if __name__ == "__main__":
    update_config_repo()  # pylint: disable=no-value-for-parameter
