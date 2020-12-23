#! /usr/bin/env python3

"""
Command-line script used to put GoCD server in maintenance mode
"""

import sys
import logging
import traceback
import re
import click
import requests
import time

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


def enable_maintenance_mode(host, token):
    """
    GoCD enable maintenance mode
    https://api.gocd.org/current/#enable-maintenance-mode
    """
    url = "https://{host}/go/api/admin/maintenance_mode/enable".format(
        host=host)

    headers = {
        'Accept': 'application/vnd.go.cd.v2+json',
        'Authorization': "bearer {token}".format(token=token),
        'X-GoCD-Confirm': "true",
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r


def disable_maintenance_mode(host, token):
    """
    GoCD disable maintenance mode
    https://api.gocd.org/current/#disable-maintenance-mode
    """
    url = "https://{host}/go/api/admin/maintenance_mode/disable".format(
        host=host)

    headers = {
        'Accept': 'application/vnd.go.cd.v2+json',
        'Authorization': "bearer {token}".format(token=token),
        'X-GoCD-Confirm': "true",
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r

def is_server_in_maintenance_mode(host, token):
    """
    GoCD check if all tasks on the server are stopped
    """
    url = "https://{host}/go/api/admin/maintenance_mode/info".format(
        host=host)

    headers = {
        'Accept': 'application/vnd.go.cd.v2+json',
        'Authorization': "bearer {token}".format(token=token),
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r


@click.command()
@click.option('--host', help='gocd hostname without protocol eg gocd.tools.edx.org', required=True)
@click.option('--token', help='gocd auth token', required=True)
@click.option('--mode', help='Enable/Disbale maintenance mode', required=False, default="enable")
def set_maintenance_mode_state(token, host, mode):
    """
    Enable or Disbale maintenance mode on GoCD server
    """
    try:
        logging.info(mode+"ing GoCD server maintenance mode ")
        if (mode == "enable"):
            enable_maintenance_mode(host, token)
            flag = True
            while flag == True:
                current_state = is_server_in_maintenance_mode(host, token)
                if is_maintenance_mode == True:
                    jobs_states = attributes["running_systems"]
                    if not jobs_states["material_update_in_progress"] or not jobs_states["building_jobs"] or not jobs_states["scheduled_jobs"]:
                        break
                    else:
                        time.sleep( 60 )
                        continue
        elif (mode == "disbale"):
            disable_maintenance_mode(host, token)
        else:
            print("Invalid mode")
    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho('{}'.format(err), fg='red')
        sys.exit(1)

if __name__ == "__main__":
    set_maintenance_mode_state()  # pylint: disable=no-value-for-parameter
