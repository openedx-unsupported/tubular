"""
Methods to interact with the Jenkins API to perform various tasks.
"""
from __future__ import unicode_literals

import logging
import os
import requests

from tubular.exception import BackendError


REQUESTS_TIMEOUT = float(os.environ.get("REQUESTS_TIMEOUT", 10))

LOG = logging.getLogger(__name__)


def trigger_build(base_url, user_name, user_token, job_name, job_token, job_cause=None, job_params=None):
    """
    Trigger a jenkins job/project (note that jenkins uses these terms interchangeably)

    Args:
        base_url (str): The base URL for the jenkins server, e.g. https://test-jenkins.testeng.edx.org
        user_name (str): The jenkins username
        user_token (str): API token for the user. Available at {base_url}/user/{user_name)/configure
        job_name (str): The Jenkins job name, e.g. test-project
        job_token (str): Jobs must be configured with the option "Trigger builds remotely" selected.
            Under this option, you must provide an authorization token (configured in the job)
            in the form of a string so that only those who know it would be able to remotely
            trigger this project's builds.
        job_cause (str): Text that will be included in the recorded build cause
        job_params (set of tuples): Parameter names and their values to pass to the job

    Returns:
        A Requests Response object

    Raises:
        BackendError: if the Jenkins job could not be triggered successfully
    """

    # Construct the URL. From the jenkins build triggers help text:
    #     Use the following URL to trigger build remotely:
    #     base_url/job/JOB_NAME/build?token=TOKEN_NAME or /buildWithParameters?token=TOKEN_NAME
    #     Optionally append &cause=Cause+Text to provide text that will be
    #     included in the recorded build cause.
    if job_params:
        build_verb = 'buildWithParameters'
    else:
        build_verb = 'build'

    url = '{base}/job/{name}/{build_verb}'.format(
        base=base_url, name=job_name, build_verb=build_verb
    )

    # Create a dict with key/value pairs from the job_params
    # that were passed in like this:  --param FOO bar --param BAZ biz
    # These will get passed to the job as string parameters like this:
    # {u'FOO': u'bar', u'BAX': u'biz'}
    request_params = {}
    for param in job_params:
        request_params[param[0]] = param[1]

    request_params.update({'token': job_token})
    if job_cause:
        request_params.update({'cause': job_cause})

    # Here is where we make the actual call to the Jenkins API
    response = requests.get(
        url,
        auth=(user_name, user_token),
        params=request_params,
        timeout=REQUESTS_TIMEOUT
    )

    # On success, Jenkins responds with a 201 Created
    if response.status_code == 201:
        return response

    # Some failure has happened.
    msg = 'Call to Jenkins failed. Status: {0}, Reason: {1}.'.format(
        response.status_code, response.reason
    )
    # Give helpful messages for the conditions that we know about.
    if response.status_code == 404:
        msg += ' Verify that you have permissions to the job and double check the spelling of its name.'
    elif response.status_code == 405:
        msg += ' Verify that you passed the required parameters to the job.'

    raise BackendError(msg)
