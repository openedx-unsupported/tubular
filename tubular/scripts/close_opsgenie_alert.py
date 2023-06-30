"""
Command-line script to submit an alert to Opsgenie Api.
"""

import logging
import sys
import traceback

import click

import tubular.opsgenie_api as opsgenie_api

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

@click.command("close_opsgenie_alert")
@click.option(
    '--auth_token',
    required=True,
    help="Authentication token to use for Opsgenie Alerts API.",
)
@click.option(
    '--alias',
    required=True,
    help="Alias of the OpsGenie alert"
)
@click.option(
    '--source',
    default=None,
    help="Source of the request"
)
def close_opsgenie_alert(auth_token, alias, source):
    """
    Close an OpsGenie alert

    Arguments:
        auth_token: API token
        alias: The alert alias
        source: The source of the request
    """
    try:
        logging.info(f"Closing alert {alias} on Opsgenie")
        opsgenie = opsgenie_api.OpsGenieAPI(auth_token)
        opsgenie.close_opsgenie_alert_by_alias(alias, source=source)
    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho('{}'.format(err), fg='red')
        sys.exit(1)


if __name__ == "__main__":
    close_opsgenie_alert()
