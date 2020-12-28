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


def switch_maintenance_mode(host, token, mode):
    """
    GoCD enable maintenance mode
    https://api.gocd.org/current/#enable-maintenance-mode
    GoCD disable maintenance mode
    https://api.gocd.org/current/#disable-maintenance-mode
    """
    url = "https://{host}/go/api/admin/maintenance_mode/{mode}".format(
        host=host, mode=mode)

    headers = {
        'Accept': 'application/vnd.go.cd.v1+json',
        'Authorization': "bearer {token}".format(token=token),
        'X-GoCD-Confirm':"true",
        'User-Agent': 'python-requests/2.25.1',
    }
    r = requests.post(url, headers=headers)
    r.raise_for_status()
    return r


def is_server_in_maintenance_mode(host, token):
    """
    GoCD check if all tasks on the server are stopped
    """
    url = "https://{host}/go/api/admin/maintenance_mode/info".format(
        host=host)

    headers = {
        'Accept': 'application/vnd.go.cd.v1+json',
        'Authorization': "bearer {token}".format(token=token),
    }
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()


@click.command()
@click.option('--host', help='gocd hostname without protocol eg gocd.tools.edx.org', required=True)
@click.option('--token', help='gocd auth token', required=True)
@click.option('--mode', help='Enable/Disbale maintenance mode', required=False, default="enable")
def set_maintenance_mode_state(token, host, mode):
    """
    Enable or Disbale maintenance mode on GoCD server
    """
    try:
        if (mode == "enable"):
            logging.info(mode[:-1]+"ing GoCD server maintenance mode ")
            switch_maintenance_mode(host, token, mode)
            logging.info("Sleeping for 10 sec")
            time.sleep( 10 )
            flag = True
            while flag == True:
                current_state = is_server_in_maintenance_mode(host, token)
                if current_state["is_maintenance_mode"] == True:
                    jobs_states = current_state["attributes"]["running_systems"]
                    if not jobs_states["material_update_in_progress"] and not jobs_states["building_jobs"] and not jobs_states["scheduled_jobs"]:
                        logging.info("All jobs are stopped. Server is now in maintenance mode")
                        break
                    else:
                        logging.info("Some jobs are in progress. Sleeping for 60 sec")
                        time.sleep( 60 )
                        continue
        elif (mode == "disable"):
            logging.info(mode[:-1]+"ing GoCD server maintenance mode ")
            switch_maintenance_mode(host, token, mode)
        else:
            logging.info("Invalid mode")
            sys.exit(1)
    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho('{}'.format(err), fg='red')
        sys.exit(1)

if __name__ == "__main__":
    set_maintenance_mode_state()  # pylint: disable=no-value-for-parameter
