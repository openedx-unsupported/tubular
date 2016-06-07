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
@click.option('--channel', '-c',
              envvar='HIPCHAT_CHANNEL',
              help="Channel to which the script should post a message. Case Sensitive.",
              )
@click.option('--message', '-m',
              help="Message to send to HipChat channel.",
              required=True
              )
def cli(auth_token, channel, message):
    """
    Post a message to a HipChat channel.
    """
    if not channel:
        print "No HIPCHAT_CHANNEL defined - ignoring message send: {}".format(message)
        sys.exit(0)

    if not auth_token:
        print "No HIPCHAT_AUTH_TOKEN defined - ignoring message send: {}".format(message)
        sys.exit(0)

    headers = {
        AUTH_HEADER_FIELD: AUTH_HEADER_VALUE.format(auth_token)
    }
    msg_payload = {
        "color": "green",
        "message": message,
        "notify": False,
        "message_format": "text"
    }
    post_url = HIPCHAT_API_URL + NOTIFICATION_POST.format(urllib.quote(channel.strip()))
    r = requests.post(post_url, headers=headers, json=msg_payload)

    # An exit code of 0 means success and non-zero means failure.
    success = r.status_code in (200, 201, 204)
    if not success:
        print "Message send failed: {}".format(r.text)
    sys.exit(not success)


if __name__ == '__main__':
    cli()
