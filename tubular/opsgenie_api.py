"""
A module to provide functionality for reading and manipulating OpsGenie.
"""

import json

from requests import Session


class OpsgenieMessageSendFailure(Exception):
    """
    Raised upon a failure to send an Opsgenie alert.
    """


class OpsGenieAPI:
    """
    A class for manipulating OpsGenie using an API Integration.
    """
    def __init__(self, auth_token):
        self.session = Session()
        self.session.headers['Authorization'] = "GenieKey {}".format(auth_token)
        self.session.headers['Content-Type'] = 'application/json'

    def alert_opsgenie(self, message, description, responders=None, alias=None,):
        """
        Alert team of an issue - such as GoCD pipeline failure

        Arguments:
            message: a summary of the issue
            description: a more detailed description
            responders: (optional) OpsGenie team name
            alias: (optional) desired alias for the alert in Opsgenie
        """
        post_url = 'https://api.opsgenie.com/v2/alerts'
        if responders is not None:
            responders = [{"name": responders, "type":"team"}]

        alert_data = {
            'message': message,
            'description': description,
            'responders': responders,
            'alias': alias,
        }

        response = self.session.post(
            url=post_url,
            data=json.dumps(alert_data)
        )

        if response.status_code not in (200, 201, 202, 204):
            raise OpsgenieMessageSendFailure(
                "Message {} failed: {}".format(message, response.text)
            )

    def close_opsgenie_alert_by_alias(self, identifier, source=None):
        """
        Close the specified OpsGenie alert

        Arguments:
            identifier: Alias of the alert to close
            source: (optional) Source of the request to close to note on the alert
        """

        post_url = f"https://api.opsgenie.com/v2/alerts/{identifier}/close" \
                   f"?identifierType=alias"

        response = self.session.post(
            url=post_url,
            data=json.dumps({
                'source': source,
                'note': f"Closed by {source if source else 'OpsGenieAPI'}"
            })
        )

        if response.status_code not in (200, 201, 202, 204):
            raise OpsgenieMessageSendFailure(
                f"Request to close {identifier} failed: {response.text}"
            )
