"""
Command-line script to submit a HipChat message to one or more channels.
"""
from __future__ import unicode_literals

import sys
import logging
from six.moves import urllib
import click
import requests


HIPCHAT_API_URL = "http://api.hipchat.com"
NOTIFICATION_POST = "/v2/room/{}/notification"
AUTH_HEADER_FIELD = "Authorization"
AUTH_HEADER_VALUE = "Bearer {}"

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


@click.command()
@click.option(
    '--auth_token', '-a',
    envvar='HIPCHAT_AUTH_TOKEN',
    help="Authentication token to use for HipChat REST API.",
)
@click.option(
    '--channels', '-c',
    envvar='HIPCHAT_CHANNELS',
    help="Channel to which the script should post a message. Case Sensitive."
         "Multiple channels can be provided as a comma separated list.",
)
@click.option(
    '--message', '-m',
    help="Message to send to HipChat channel.",
    required=True
)
@click.option(
    '--color',
    envvar='HIPCHAT_COLOR',
    default="green",
    help='The color of the message in HipChat.',
)
def cli(auth_token, channels, message, color):
    """
    Post a message to one or more HipChat channels.
    """
    if not channels.strip():
        logging.warning("No HIPCHAT_CHANNELS defined - ignoring message send: {}".format(message))
        sys.exit(0)

    # Convert the comma seperate string to a list of names, and remove any empty strings.
    # This handles the case where there is a trailing comma or multiple commas with no
    # text in between them.
    channel_list = [channel.strip() for channel in channels.split(",") if channel.strip()]
    if len(channel_list) < 1:
        logging.warning("HIPCHAT_CHANNELS defined a list with no valid channel names - "
                        "ignoring message send: {}".format(message))
        sys.exit(0)

    if not auth_token:
        logging.warning("No HIPCHAT_AUTH_TOKEN defined - ignoring message send: {}".format(message))
        sys.exit(0)

    headers = {
        AUTH_HEADER_FIELD: AUTH_HEADER_VALUE.format(auth_token)
    }
    msg_payload = {
        "color": color,
        "message": message,
        "notify": False,
        "message_format": "text"
    }

    for channel in channel_list:
        post_url = HIPCHAT_API_URL + NOTIFICATION_POST.format(urllib.parse.quote(channel))
        response = requests.post(post_url, headers=headers, json=msg_payload)

        if response.status_code not in (200, 201, 204):
            logging.error("Message send failed: {}".format(response.text))
            # An exit code of 0 means success and non-zero means failure.
            sys.exit(1)

    # An exit code of 0 means success and non-zero means failure.
    sys.exit(0)


if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter
