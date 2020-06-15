#! /usr/bin/env python3

"""
Command-line script to submit a Slack message to one or more channels.
"""

import sys
from os import path

import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.slack import submit_slack_message  # pylint: disable=wrong-import-position


@click.command()
@click.option(
    '--auth_token',
    required=True,
    help="Authentication token to use for Slack REST API.",
)
@click.option(
    '--channel',
    multiple=True,
    required=True,
    help="Channel to which the script should post a message. Case Sensitive."
)
@click.option(
    '--message',
    required=True,
    help="Message to send to Slack channel.",
)
def submit_slack_msg(auth_token, channel, message):
    """
    Post a message to one or more Slack channels.
    """
    submit_slack_message(auth_token, channel, message)
    # An exit code of 0 means success and non-zero means failure.
    sys.exit(0)


if __name__ == '__main__':
    submit_slack_msg()  # pylint: disable=no-value-for-parameter
