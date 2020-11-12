"""
Command-line script to submit an alert to Opsgenie Api.
"""
import click

from tubular.opsgenie_api import OpsGenieAPI


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
    opsgenie = OpsGenieAPI(auth_token)

    opsgenie.alert_opsgenie(message, description)
