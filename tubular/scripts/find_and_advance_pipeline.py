#! /usr/bin/env python3

"""
Command-line script to find the next release pipeline to advance
and then advance it by triggering the manual stage.
"""

import logging
import os
import sys
from os import path

import click
import yaml
from dateutil import parser

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.gocd_api import GoCDAPI  # pylint: disable=wrong-import-position
from tubular.slack import submit_slack_message  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


@click.command()
@click.option(
    '--gocd_username',
    help=u"Username to use in logging into GoCD.",
    required=True,
)
@click.option(
    '--gocd_password',
    help=u"Password to use in logging into GoCD.",
    required=True,
)
@click.option(
    '--gocd_url',
    help=u"URL to use in logging into GoCD.",
    required=True,
)
@click.option(
    '--slack_token',
    help=u"Slack token which authorizes message sending. (optional)",
)
@click.option(
    '--slack_room',
    multiple=True,
    help=u"Slack channel which to send the message. (optional)",
)
@click.option(
    '--pipeline',
    help=u"Name of the pipeline to advance.",
    required=True,
)
@click.option(
    '--stage',
    help=u"Name of the pipeline's stage to advance.",
    required=True,
)
@click.option(
    '--check_ci_stage',
    help=u"Name of the pipeline's optional ci_check stage.",
)
@click.option(
    '--relative_dt',
    help=u"Datetime used when determining current release date in ISO 8601 format, YYYY-MM-DDTHH:MM:SS+HH:MM",
)
@click.option(
    '--out_file',
    help=u"File location in which to write CI test status info.",
    type=click.File(mode='w', lazy=True),
    default=sys.stdout
)
def find_and_advance_pipeline(
        gocd_username, gocd_password, gocd_url, slack_token, slack_room,
        pipeline, stage, check_ci_stage, relative_dt, out_file

):
    """
    Find the GoCD advancement pipeline that should be advanced/deployed to production - and advance it.
    """
    gocd = GoCDAPI(gocd_username, gocd_password, gocd_url)

    # If a datetime string was passed-in, convert it to a datetime.
    if relative_dt:
        relative_dt = parser.parse(relative_dt)

    pipeline_to_advance = gocd.fetch_pipeline_to_advance(pipeline, stage, check_ci_stage, relative_dt)
    gocd.approve_stage(
        pipeline_to_advance.name,
        pipeline_to_advance.counter,
        stage
    )
    advance_info = {
        'name': pipeline_to_advance.name,
        'counter': pipeline_to_advance.counter,
        'stage': stage,
        'url': pipeline_to_advance.url
    }
    LOG.info('Successfully advanced this pipeline: %s', advance_info)

    dirname = os.path.dirname(out_file.name)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    yaml.safe_dump(advance_info, stream=out_file)

    if slack_token:
        submit_slack_message(
            slack_token,
            slack_room,
            'PROD DEPLOY: Pipeline was advanced: {}'.format(pipeline_to_advance.url)
        )


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    find_and_advance_pipeline()
