#!/usr/bin/env python
import sys
import logging
import requests
import click
import urllib


HIPCHAT_API_URL = "http://api.hipchat.com"
NOTIFICATION_POST = "/v2/room/{}/notification"
AUTH_HEADER_FIELD = "Authorization"
AUTH_HEADER_VALUE = "Bearer {}"


logging.basicConfig(stream=sys.stdout, level=logging.INFO)

@click.command()
@click.option('--auth_token', '-a',
              envvar='HIPCHAT_AUTH_TOKEN',
              help="Authentication token to use for HipChat REST API.",
              )
@click.option('--channels', '-c',
              envvar='HIPCHAT_CHANNELS',
              help="Channel to which the script should post a message. Case Sensitive."
                   "Multiple channels can be provided as a comma separated list.",
              )
@click.option('--message', '-m',
              help="Message to send to HipChat channel.",
              required=True
              )
@click.option('--color',
              envvar='HIPCHAT_COLOR',
              default="green",
              help='The color of the message in HipChat.',
              )
def cli(auth_token, channels, message, color):
    """
    Post a message to a HipChat channels.
    """
    if not channel:
        print "No HIPCHAT_CHANNELS defined - ignoring message send: {}".format(message)
        sys.exit(0)

    if not auth_token:
        print "No HIPCHAT_AUTH_TOKEN defined - ignoring message send: {}".format(message)
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

    channel_list = [channel.strip() for channel in channels.split(",")]
    for channel in channel_list:
        # Empty channel names can happen if people put in double commas or
        # if there is a trailing comma in the channels list.
        if not channel:
            continue

        post_url = HIPCHAT_API_URL + NOTIFICATION_POST.format(urllib.quote(channel))
        r = requests.post(post_url, headers=headers, json=msg_payload)

        if not r.status_code in (200, 201, 204):
            print "Message send failed: {}".format(r.text)
            # An exit code of 0 means success and non-zero means failure.
            sys.exit(1)

    # An exit code of 0 means success and non-zero means failure.
    sys.exit(0)


if __name__ == '__main__':
    cli()
