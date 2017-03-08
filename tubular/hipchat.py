""" Commands to interact with the HipChat API. """
from __future__ import absolute_import
from __future__ import print_function, unicode_literals

import logging
from six.moves import urllib
import requests

HIPCHAT_API_URL = "http://api.hipchat.com"
NOTIFICATION_POST = "/v2/room/{}/notification"
AUTH_HEADER_FIELD = "Authorization"
AUTH_HEADER_VALUE = "Bearer {}"

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)


class HipChatMessageSendFailure(Exception):
    """
    Raised upon a failure to send a HipChat message to a channel.
    """
    pass


def submit_hipchat_message(auth_token, channels, message, color=None):
    """
    Post a message to one or more HipChat channels.

    Args:
        auth_token (str): HipChat authentication token which authorizes message posting.
        channels (list(str)): List of channel names to which to post the message.
        message (str): Message to post to HipChat channel.
        color (str): Color to use when posting message, i.e. "green", "red".
    """
    headers = {
        AUTH_HEADER_FIELD: AUTH_HEADER_VALUE.format(auth_token)
    }
    msg_payload = {
        "message": message,
        "notify": False,
        "message_format": "text"
    }
    if color:
        msg_payload['color'] = color

    for channel in channels:
        post_url = HIPCHAT_API_URL + NOTIFICATION_POST.format(urllib.parse.quote(channel))
        response = requests.post(post_url, headers=headers, json=msg_payload)

        if response.status_code not in (200, 201, 204):
            raise HipChatMessageSendFailure(
                "Message send to channel '{}' failed: {}".format(channel, response.text)
            )
