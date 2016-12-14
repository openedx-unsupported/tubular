"""
Methods to interact with the Jenkins API to perform various tasks.
"""
import logging

import backoff
from jenkinsapi.jenkins import Jenkins
from jenkinsapi.custom_exceptions import JenkinsAPIException
from requests.exceptions import HTTPError

from tubular.exception import BackendError

LOG = logging.getLogger(__name__)

MAX_TRIES = 12


def trigger_build(base_url, user_name, user_token, job_name, job_token, job_cause=None, job_params=None):
    u"""
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
        A the status of the build that was triggered

    Raises:
        BackendError: if the Jenkins job could not be triggered successfully
    """
    def poll_giveup(data):
        u""" Raise an error when the polling tries are exceeded."""
        orig_args = data.get(u'args')
        # The Build object was the only parameter to the original method call,
        # and so it's the first and only item in the args.
        build = orig_args[0]
        msg = u'Timed out waiting for build {} to finish.'.format(build.name)
        raise BackendError(msg)

    @backoff.on_predicate(
        backoff.expo,
        max_tries=MAX_TRIES,
        on_giveup=poll_giveup
    )
    def poll_build_for_result(build):
        u"""
        Poll for the build running, with exponential backoff.
        The on_predicate decorator is used to retry when the return value
        of the target function is True.

        Warning: setting MAX_TRIES to 0 will loop infinitely.
        Here is a chart to help you decide on a good value to use, showing
        exponential backoff with a base of 2 and factor of 1 (defaults for backoff.expo)

        |wait x sec|make attempt #|total time (sec)|total time (min)|
        |----:|---:|----:|-----:|
        |0    |1   |0    | 0    |
        |1    |2   |1    |0.02  |
        |2    |3   |3    |0.05  |
        |4    |4   |7    |0.12  |
        |8    |5   |15   |0.25  |
        |16   |6   |31   |0.52  |
        |32   |7   |63   |1.05  |
        |64   |8   |127  |2.12  |
        |128  |9   |255  |4.25  |
        |256  |10  |511  |8.52  |
        |512  |11  |1023 |17.05 |
        |1024 |12  |2047 |34.12 |
        |2048 |13  |4095 |68.25 |
        """
        return not build.is_running()

    # Create a dict with key/value pairs from the job_params
    # that were passed in like this:  --param FOO bar --param BAZ biz
    # These will get passed to the job as string parameters like this:
    # {u'FOO': u'bar', u'BAX': u'biz'}
    request_params = {}
    for param in job_params:
        request_params[param[0]] = param[1]

    # Contact jenkins, log in, and get the base data on the system.
    try:
        jenkins = Jenkins(base_url, username=user_name, password=user_token)
    except (JenkinsAPIException, HTTPError) as err:
        raise BackendError(err.message)

    if not jenkins.has_job(job_name):
        msg = u'Job not found: {}.'.format(job_name)
        msg += u' Verify that you have permissions for the job and double check the spelling of its name.'
        raise BackendError(msg)

    # This will start the job and will return a QueueItem object which can be used to get build results
    job = jenkins[job_name]
    queue_item = job.invoke(securitytoken=job_token, build_params=request_params, cause=job_cause)
    LOG.info(queue_item)

    # Block this script until we are through the queue and the job has begun to build.
    queue_item.block_until_building()
    build = queue_item.get_build()
    LOG.info(build)

    # Now block until you get a result back from the build.
    poll_build_for_result(build)
    status = build.get_status()
    LOG.info(u'Build status: {status}'.format(status=status))
    return status
