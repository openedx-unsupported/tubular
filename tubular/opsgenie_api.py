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

    def set_team_members(self, team_id, member_usernames):
        """
        Set members of the specified team to be the specified usernames.

        Arguments:
            team_id: The id of the team to modify
            member_usernames: A list of OpsGenie usernames
        """
        data = json.dumps({
            'members': [
                {'user': {'username': username}}
                for username in member_usernames
            ]
        })
        result = self.session.patch(
            url='https://api.opsgenie.com/v2/teams/{}'.format(team_id),
            data=data
        )

        result.raise_for_status()
        return result

    def alert_opsgenie(self, message, description):
        """
        Alert team of an issue - such as GoCD pipeline failure

        Arguments:
            message: a summary of the issue
            description: a more detailed description
        """
        post_url = 'https://api.opsgenie.com/v2/alerts'

        alert_data = {
            'message': message,
            'description': description,
        }

        response = self.session.post(
            url=post_url,
            data=json.dumps(alert_data)
        )

        if response.status_code not in (200, 201, 204):
            raise OpsgenieMessageSendFailure(
                "Message {} failed: {}".format(message, response.text)
            )
