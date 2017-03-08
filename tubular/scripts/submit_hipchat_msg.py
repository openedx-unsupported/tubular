#! /usr/bin/env python3

"""
Command-line script to submit a HipChat message to one or more channels.
"""
from __future__ import absolute_import
from __future__ import unicode_literals

from os import path
import sys
import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.hipchat import submit_hipchat_message  # pylint: disable=wrong-import-position


@click.command()
@click.option(
    '--auth_token',
    required=True,
    help="Authentication token to use for HipChat REST API.",
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
    help="Message to send to HipChat channel.",
)
@click.option(
    '--color',
    default="green",
    help='The color of the message in HipChat.',
)
def submit_hipchat_msg(auth_token, channel, message, color):
    """
    Post a message to one or more HipChat channels.
    """
    submit_hipchat_message(auth_token, channel, message, color)

    # An exit code of 0 means success and non-zero means failure.
    sys.exit(0)


if __name__ == '__main__':
    submit_hipchat_msg()  # pylint: disable=no-value-for-parameter
