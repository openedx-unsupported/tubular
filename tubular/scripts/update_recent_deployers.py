"""
A script for updating an OpsGenie team to contain all users whose changes
were deployed within a specific timewindow via a specified GoCD pipeline.
"""

import re

import click
import yaml
from requests.exceptions import HTTPError

from tubular.github_api import GitHubAPI
from tubular.gocd_api import GoCDAPI  # pylint: disable=wrong-import-position
from tubular.opsgenie_api import OpsGenieAPI


def _parse_pipeline_def(_ctx, _param, values):
    """
    Parse the --pipeline argument into pairs of (pipeline, stages)
    """
    parsed = []
    for value in values:
        match = re.match(r'(?P<pipeline>.*)\[(?P<stages>.*)\]', value)
        if match is None:
            raise ValueError("{!r} does not match format pipeline[stage, ...]")

        pipeline, stages = match.group('pipeline', 'stages')
        parsed.append((pipeline, [stage.strip() for stage in stages.split(',')]))
    return parsed


@click.command()
@click.password_option(
    '--api-key', 'opsgenie_api_key', required=True,
    help="The OpsGenie API Integration Key to use for authentication"
)
@click.option(
    '--team-id', 'opsgenie_team_id', required=True,
    help="The ID of the OpsGenie Team to set to recent deployers")
@click.option(
    '--pipelines', 'gocd_pipelines', multiple=True, required=True, callback=_parse_pipeline_def,
    help=(
            "The name of the deployment pipeline and the stages in it that "
            "trigger deployment actions. The format for each pipeline is pipeline_name[stage, stage]"
    )
)
@click.option(
    '--username', 'gocd_username', required=True,
    help="The username to authenticate with GoCD")
@click.password_option(
    '--password', 'gocd_password', required=True,
    help="The password to authenticate with GoCD")
@click.option(
    '--gocd-url', 'gocd_url', required=True,
    help="Url for the GoCD server to connect to")
@click.password_option(
    '--token', 'github_token', required=True,
    help="Github Token to download people.yaml with")
@click.option(
    '--recent-cutoff', 'recent_cutoff', default=30, show_default=True, type=int,
    help="Number of minutes to consider as being recent")
def update_recent_deployers(
        opsgenie_api_key,
        opsgenie_team_id,
        gocd_pipelines,
        gocd_username,
        gocd_password,
        gocd_url,
        github_token,
        recent_cutoff=30
):
    """
    Update an OpsGenie team to contain only those users whose changes were recently deployed
    by a particular GoCD pipeline.
    """
    repo_tools_repo = GitHubAPI('edx', 'repo-tools-data', github_token)
    people_yaml_data = repo_tools_repo.file_contents('people.yaml')
    people_yaml = yaml.safe_load(people_yaml_data)

    email_aliases = {
        gh: [user['email']] + user.get('other_emails', [])
        for gh, user in people_yaml.items()
    }

    gocd = GoCDAPI(gocd_username, gocd_password, gocd_url)
    recent_deployers = set().union(*(
        gocd.recent_deployers(pipeline, stages, cutoff=recent_cutoff, email_aliases=email_aliases)
        for pipeline, stages in gocd_pipelines
    ))

    opsgenie = OpsGenieAPI(opsgenie_api_key)

    while True:
        try:
            opsgenie.set_team_members(opsgenie_team_id, recent_deployers)
            break
        except HTTPError as exc:
            if exc.response.status_code == 422:
                message = exc.response.json().get('message')

                if message is None:
                    raise

                match = re.match(r"No user exists with username \[(?P<user>.*)\]", message)

                if match is None:
                    raise

                user = match.group('user')
                click.echo(click.style('Removing user {!r} and retrying'.format(user), fg='red'))
                recent_deployers.remove(user)
                continue
            raise

    # TODO: Make escalation to the non-deployers team happen immediately if recent-deployers is empty
