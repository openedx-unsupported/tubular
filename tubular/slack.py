""" Commands to interact with the Slack API. """
from __future__ import absolute_import
from __future__ import print_function, unicode_literals

import logging
import requests

SLACK_API_URL = "https://slack.com"
NOTIFICATION_POST = "/api/chat.postMessage"
AUTH_HEADER_FIELD = "Authorization"
AUTH_HEADER_VALUE = "Bearer {}"

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)


class SlackMessageSendFailure(Exception):
    """
    Raised upon a failure to send a Slack message to a channel.
    """
    pass


def submit_slack_message(auth_token, channels, message):
    """
    Post a message to one or more slack channels.

    Args:
        auth_token (str): Slack authentication token which authorizes message posting.
        channels (list(str)): List of channel names to which to post the message.
        message (str): Message to post to Slack channel.
    """
    post_url = SLACK_API_URL + NOTIFICATION_POST
    headers = {
        AUTH_HEADER_FIELD: AUTH_HEADER_VALUE.format(auth_token)
    }

    msg_payload = {
        "text": message,
    }

    for channel in channels:
        msg_payload["channel"] = channel
        response = requests.post(post_url, json=msg_payload, headers=headers)

        if response.status_code not in (200, 201, 204):
            raise SlackMessageSendFailure(
                "Message send to channel '{}' failed: {}".format(channel, response.text)
            )
