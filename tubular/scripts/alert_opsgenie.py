"""
Command-line script to submit an alert to Opsgenie Api.
"""

import logging
import sys
import traceback

import click

import tubular.opsgenie_api as opsgenie_api

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)

@click.command("alert_opsgenie")
@click.option(
    '--auth_token',
    required=True,
    help="Authentication token to use for Opsgenie Alerts API.",
)
@click.option(
    '--message',
    required=True,
    help="Message in the subject of Opsgenie Alert",
)
@click.option(
    '--description',
    required=True,
    help="Message in the body of Opsgenie Alert",
)
@click.option(
    '--responders',
    default=None,
    help="Who will be paged for this alert",
)
@click.option(
    '--alias',
    default=None,
    help="Alias of the OpsGenie alert"
)
def alert_opsgenie(auth_token, message, description, responders, alias):
    """
    Create an OpsGenie alert

    Arguments:
        auth_token: API token
        message: The alert message
        description: The alert description
        responders: The team responsible for the alert
        alias: The alert alias
    """
    try:
        logging.info("Creating alert on Opsgenie")
        opsgenie = opsgenie_api.OpsGenieAPI(auth_token)
        opsgenie.alert_opsgenie(message, description, responders, alias=alias)
    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho('{}'.format(err), fg='red')
        sys.exit(1)


if __name__ == "__main__":
    alert_opsgenie()
