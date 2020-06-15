#! /usr/bin/env python3

"""
Command-line script to click the "manual" gate in gocd.
"""

# pylint: disable=invalid-name

import os
import sys

import click
from yagocd import Yagocd

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@click.command()
@click.option(
    '--go-server-url',
    required=True,
    help='The URL for the GoCD server to interact with.',
)
@click.option(
    '--username',
    required=True,
    help='The username of the user to use when hitting the GoCD API.',
)
@click.option(
    '--secret',
    required=True,
    help='The secret to use for auth with the GoCD API.',
)
@click.option(
    '--pipeline-name',
    required=True,
    help='The name of the pipeline to affect.',
)
@click.option(
    '--pipeline-counter',
    required=True,
    help='The number associated with this particular run of the pipeline.',
)
@click.option(
    '--stage-name',
    required=True,
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
