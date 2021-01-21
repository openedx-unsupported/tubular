#! /usr/bin/env python3

"""
Command-line script to trigger a jenkins job
"""

from os import path
import sys

import click
import click_log
from jenkinsapi.constants import STATUS_FAIL, STATUS_ERROR, STATUS_ABORTED, STATUS_REGRESSION, STATUS_SUCCESS

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
    required=True,
)
@click.option(
    "--user_token",
    help="API token for the user. Available at {url}/user/{user_name)/configure",
    type=str,
    envvar='JENKINS_USER_TOKEN'
)
@click.option(
    "--job",
    help="The name of the jenkins job. E.g. test-project",
    type=str,
    required=True,
)
@click.option(
    "--token",
    help="The authorization token for the job. Must match that configured in the job definition.",
    type=str,
    envvar='JENKINS_JOB_TOKEN'
)
@click.option(
    "--cause",
    help="Text that will be included in the recorded build cause.",
    type=str,
    required=False,
)
@click.option(
    "--param",
    help="Key/value pairs to pass to the job as parameters. E.g. --param FOO bar --param BAZ biz",
    multiple=True,
    required=False,
    type=(str, str)
)
@click.option(
    "--timeout",
    help="Maximum duration to wait for the jenkins job to complete (measured from "
         "the time the job is triggered), in seconds.",
    type=float,
    required=False,
    default=30 * 60,
)
@click.option(
    "--expected-status",
    help="The expected job status once the job completes.",
    default=STATUS_SUCCESS,
    type=click.Choice([
        STATUS_FAIL,
        STATUS_ERROR,
        STATUS_ABORTED,
        STATUS_REGRESSION,
        STATUS_SUCCESS,
    ])
)
@click_log.simple_verbosity_option(default='INFO')
def trigger(url, user_name, user_token, job, token, cause, param, timeout, expected_status):
    """Trigger a jenkins job. """
    status = jenkins.trigger_build(url, user_name, user_token, job, token, cause, param, timeout)
    if status != expected_status:
        raise click.ClickException(f'Job finished with unexpected status {status}')

if __name__ == "__main__":
    trigger()  # pylint: disable=no-value-for-parameter
