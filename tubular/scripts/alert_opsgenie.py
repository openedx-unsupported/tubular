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
@click.option(
    '--team_id',
    required=True,
    help="Team id to notify for Opsgenei Alert",
)
def alert_opsgenie(auth_token, message, description, team_id):
    """
    Sends an alert to an opsgenie team
    """
    opsgenie = OpsGenieAPI(auth_token)

    opsgenie.alert_opsgenie(message, description, team_id)
