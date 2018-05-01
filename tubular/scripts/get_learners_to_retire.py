#! /usr/bin/env python3

"""
Command-line script to retrieve list of learners that have requested to be retired.
The script calls the appropriate LMS endpoint to get this list of learners.
"""
from __future__ import absolute_import
from __future__ import unicode_literals

from os import path
import io
import sys
import logging
import click
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.edx_api import LmsApi  # pylint: disable=wrong-import-position
from tubular.jenkins import export_learner_job_properties  # pylint: disable=wrong-import-position

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
LOG = logging.getLogger(__name__)


@click.command()
@click.option(
    '--config_file',
    help='File in which YAML config exists that overrides all other params.'
)
@click.option(
    '--client_id',
    help='ID of OAuth client used in svr-to-svr client credentials grant.'
)
@click.option(
    '--client_secret',
    help='Secret associated with OAuth client used in svr-to-svr client credentials grant.'
)
@click.option(
    '--lms_base_url',
    help='Base URL of LMS from which to retrieve learner list, including :<port> if non-standard.',
    default='http://localhost'
)
@click.option(
    '--cool_off_days',
    help='Number of days a learner should be in the retirement queue before being actually retired.',
    default='7'
)
@click.option(
    '--output_dir',
    help="Directory in which to write the Jenkins properties files.",
    default='./jenkins_props'
)
def get_learners_to_retire(config_file,
                           client_id,
                           client_secret,
                           lms_base_url,
                           cool_off_days,
                           output_dir):
    """
    Retrieves a JWT token as the retirement service user, then calls the LMS
    endpoint to retrieve the list of learners awaiting retirement.
    """
    if config_file:
        # If a config file is present, it overrides all passed-in params.
        with io.open(config_file, 'r') as config:
            config_yaml = yaml.load(config)
        client_id = config_yaml['client_id']
        client_secret = config_yaml['client_secret']
        lms_base_url = config_yaml['base_urls']['lms']

    api = LmsApi(lms_base_url, lms_base_url, client_id, client_secret)

    # Retrieve the learners to retire and export them to separate Jenkins property files.
    export_learner_job_properties(
        api.learners_to_retire(cool_off_days),
        output_dir
    )


if __name__ == "__main__":
    # pylint: disable=unexpected-keyword-arg, no-value-for-parameter
    # If using env vars to provide params, prefix them with "RETIREMENT_", e.g. RETIREMENT_CLIENT_ID
    get_learners_to_retire(auto_envvar_prefix='RETIREMENT')
