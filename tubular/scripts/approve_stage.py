#! /usr/bin/env python3

"""
Command-line script to click the "manual" gate in gocd.
"""

# pylint: disable=invalid-name
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

import os
import sys
import click
from yagocd import Yagocd

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@click.command()
@click.option(
    '--go-server-url',
    envvar='GOCD_SERVER_URL',
    help='The URL for the GoCD server to interact with.',
)
@click.option(
    '--username',
    envvar='GOCD_AUTOMATION_USER_NAME',
    help='The username of the user to use when hitting the GoCD API.',
)
@click.option(
    '--secret',
    envvar='GOCD_AUTOMATION_USER_SECRET',
    help='The secret to use for auth with the GoCD API.',
)
@click.option(
    '--pipeline-name',
    envvar='GOCD_PIPELINE_NAME',
    help='The name of the pipeline to affect.',
)
@click.option(
    '--pipeline-counter',
    envvar='GOCD_PIPELINE_COUNTER',
    help='The number associated with this particular run of the pipeline.',
)
@click.option(
    '--stage-name',
    envvar='GOCD_STAGE_NAME',
    help='The stage that requires "manual" approval.',
)
def approve_stage(go_server_url, username, secret, pipeline_name, pipeline_counter, stage_name):
    """
    Approves the specified stage of the specified pipeline run, as the given user.
    """
    client = Yagocd(
        server=go_server_url,
        auth=(username, secret),
    )
    client.stages.run(pipeline_name, pipeline_counter, stage_name)

if __name__ == "__main__":
    approve_stage()  # pylint: disable=no-value-for-parameter
