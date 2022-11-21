""" Commands to interact with the Slack API. """

import logging
import requests

SLACK_API_URL = "https://slack.com"
NOTIFICATION_POST = "/api/chat.postMessage"
CONTENT_TYPE = "application/json"
AUTH_HEADER_FIELD = "Authorization"

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)


class SlackMessageSendFailure(Exception):
    """
    Raised upon a failure to send a Slack message to a channel.
    """


def submit_slack_message(auth_token, channels, message):
    """
    Post a message to one or more slack channels.

    Args:
        auth_token (str): Slack authentication token which authorizes message posting.
        channels (list(str)): List of channel names to which to post the message.
        message (str): Message to post to Slack channel.
    """
    post_url = "{}{}".format(SLACK_API_URL, NOTIFICATION_POST)
    # to remove slack API warning
    headers = {
        'Content-type': CONTENT_TYPE
    }
    for channel in channels:
        params = {
            "token": auth_token,
            "channel": channel,
            "text": message
        }
        response = requests.post(post_url,
                                 params=params,
                                 headers=headers
                                 )
        if response.status_code not in (200, 201, 204):
            raise SlackMessageSendFailure(
                f"Message send to channel '{channel}' failed: {response.text}"
            )
        response_json = response.json()
        if not response_json.ok:
            # note that this should be a failure but slack messages
            # aren't that big a deal so we don't want an error code
            # here.
            LOG.warning(
                f"Message send to channel '{channel}' failed: {response.text}"
            )
