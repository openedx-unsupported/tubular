"""
Command-line script to trigger a jenkins job
"""
from __future__ import unicode_literals

import sys
from os import path
import click

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular import jenkins  # pylint: disable=wrong-import-position


@click.command()
@click.option(
    "--url",
    help="The base jenkins URL. E.g. https://test-jenkins.testeng.edx.org",
    type=str,
    required=True,
    default="https://test-jenkins.testeng.edx.org"
)
@click.option(
    "--user_name",
    help="The Jenkins username for triggering the job.",
    type=str,
    required=True
)
@click.option(
    "--user_token",
    help="API token for the user. Available at {url}/user/{user_name)/configure",
    type=str,
    required=True
)
@click.option(
    "--job",
    help="The name of the jenkins job. E.g. test-project",
    type=str,
    required=True
)
@click.option(
    "--token",
    help="The authorization token for the job. Must match that configured in the job definition.",
    type=str,
    required=True
)
@click.option(
    "--cause",
    help="Text that will be included in the recorded build cause.",
    type=str,
    required=False
)
@click.option(
    '--param',
    help='Key/value pairs to pass to the job as parameters. E.g. --param FOO bar --param BAZ biz',
    multiple=True,
    required=False,
    type=(str, str)
)
def trigger(url, user_name, user_token, job, token, cause, param):
    """
    Trigger a jenkins job.
    """
    jenkins.trigger_build(url, user_name, user_token, job, token, cause, param)

if __name__ == "__main__":
    trigger()  # pylint: disable=no-value-for-parameter
