"""
Command-line script to submit an alert to Opsgenie Api.
"""

import sys
import logging
import traceback
import click

from tubular.opsgenie_api import OpsGenieAPI

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
def alert_opsgenie(auth_token, message, description):
    """
    Sends an alert to an opsgenie team
    """
    try:
        logging.info("Creating alert on Opsgenie")
        opsgenie = OpsGenieAPI(auth_token)
        opsgenie.alert_opsgenie(message, description)
    except Exception as err:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho('{}'.format(err), fg='red')
        sys.exit(1)

if __name__ == "__main__":
    alert_opsgenie()
