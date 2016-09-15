from datetime import datetime,timedelta
import os
import logging
import requests
import time
import traceback
import tubular.ec2 as ec2

from collections import defaultdict
from tubular.utils.retry import retry
from tubular.exception import (
        BackendError,
        BackendDataError,
        ASGDoesNotExistException,
        CannotDisableActiveASG,
        CannotDeleteActiveASG,
        CannotDeleteLastASG,
        ResourceDoesNotExistException,
        TimeoutException,
        ClusterDoesNotExistException,
)
from utils import WAIT_SLEEP_TIME

ASGARD_API_ENDPOINT = os.environ.get("ASGARD_API_ENDPOINTS", "http://dummy.url:8091/us-east-1")
ASGARD_API_TOKEN = "asgardApiToken={}".format(os.environ.get("ASGARD_API_TOKEN", "dummy-token"))
ASGARD_WAIT_TIMEOUT = int(os.environ.get("ASGARD_WAIT_TIMEOUT", 600))
REQUESTS_TIMEOUT = float(os.environ.get("REQUESTS_TIMEOUT", 10))

CLUSTER_LIST_URL= "{}/cluster/list.json".format(ASGARD_API_ENDPOINT)
ASG_ACTIVATE_URL= "{}/cluster/activate".format(ASGARD_API_ENDPOINT)
ASG_DEACTIVATE_URL= "{}/cluster/deactivate".format(ASGARD_API_ENDPOINT)
ASG_DELETE_URL= "{}/cluster/delete".format(ASGARD_API_ENDPOINT)
NEW_ASG_URL= "{}/cluster/createNextGroup".format(ASGARD_API_ENDPOINT)
ASG_INFO_URL="{}/autoScaling/show/{}.json".format(ASGARD_API_ENDPOINT, "{}")
CLUSTER_INFO_URL = "{}/cluster/show/{}.json".format(ASGARD_API_ENDPOINT, "{}")

LOG = logging.getLogger(__name__)


@retry()
def clusters_for_asgs(asgs):
    """
    An autoscaling group can belong to multiple clusters potentially.

    This function finds all asgard clusters for a list of ASGs.
    eg. get all clusters that have the 'edxapp' cluster tag..

    Arguments::
        asgs(iterable): A iterable of ASGs we care about.
    eg.
    [
        u'test-edx-edxapp-v007',
        u'test-edx-worker-v007',
    ]


    Returns:
        dict: A mapping of cluster names to asgs in the cluster.

    eg.
    {
        u'test-edx-edxapp': [
            u'test-edx-edxapp-v007',
        ],
        u'test-edx-worker': [
            u'test-edx-worker-v004',
        ]
    }

    Raises:
        BackendDataError: We got bad data from the backend. We can't
            get cluster information from it.
    """

    request = requests.Request('GET', CLUSTER_LIST_URL, params=ASGARD_API_TOKEN)
    url = request.prepare().url
    LOG.debug("Getting Cluster List from: {}".format(url))
    response = requests.get(CLUSTER_LIST_URL, params=ASGARD_API_TOKEN, timeout=REQUESTS_TIMEOUT)
    try:
        cluster_json = response.json()
    except ValueError as e:
        msg = "Expected json info for asg from {} but got the following:\n{}"
        raise BackendError(msg.format(url, response.text))

    # need this to be a list so that we can test membership.
    asgs = list(asgs)

    relevant_clusters = {}
    for cluster in cluster_json:
        if "autoScalingGroups" not in cluster or "cluster" not in cluster:
            msg = "Expected 'cluster' and 'autoScalingGroups' keys in dict: {}".format(cluster)
            raise BackendDataError(msg)

        for asg in cluster['autoScalingGroups']:
            LOG.debug("Membership: {} in {}: {}".format(asg, asgs, asg in asgs))
            if asg in asgs:
                relevant_clusters[cluster['cluster']] = cluster['autoScalingGroups']
                # A cluster can have multiple relevant ASGs.
                # We don't need to check them all.
                break # The inner for loop

    return relevant_clusters


@retry()
def asgs_for_cluster(cluster):
    """
    Given a named cluster, get all ASGs in the cluster.

    Arguments:
        cluster(str): The name of the asgard cluster.

    Returns:
        list: List of ASGs.
    """

    LOG.debug("URL: {}".format(CLUSTER_INFO_URL.format(cluster)))
    url = CLUSTER_INFO_URL.format(cluster)
    response = requests.get(url, params=ASGARD_API_TOKEN, timeout=REQUESTS_TIMEOUT)

    LOG.debug("ASGs for Cluster: {}".format(response.text))
    asgs = response.json()

    try:
        asg_names = map(lambda x: x['autoScalingGroupName'], asgs)
    except (KeyError,TypeError) as e:
        msg = "Expected a list of dicts with an 'autoScalingGroupName' attribute. " \
              "Got: {}".format(asgs)
        raise BackendDataError(msg)

    return asg_names


def wait_for_task_completion(task_url, timeout):
    """
    Arguments:
        task_url(str): The URL from which to retrieve task status.
        timeout(int): How many seconds to wait for task completion
                      before throwing an error.

    Returns:
        dict: Parsed json of the task completion or failure status.

    Raises:
        TimeoutException: When we timeout waiting for the task to finish.
    """

    if not task_url.endswith('.json'):
        task_url += ".json"

    LOG.debug("Task URL: {}".format(task_url))
    end_time = datetime.utcnow() + timedelta(seconds=timeout)
    while end_time > datetime.utcnow():
        response = requests.get(task_url, params=ASGARD_API_TOKEN, timeout=REQUESTS_TIMEOUT)
        status = response.json()['status']
        if status == 'completed' or status == 'failed':
            try:
                return response.json()
            except ValueError as e:
                msg = "Expected json status for task {} but got the following:\n{}"
                raise BackendError(msg.format(task_url, response.text))

        time.sleep(WAIT_SLEEP_TIME)

    raise TimeoutException("Timed out while waiting for task {}".format(task_url))


def new_asg(cluster, ami_id):
    """
    Create a new ASG in the given asgard cluster using the given AMI.

    Arguments:
        cluster(str): Name of the cluster.
        ami_id(str): AWS AMI ID

    Returns:
        str: The name of the new ASG.

    Raises:
        TimeoutException: When the task to bring up the new ASG times out.
        BackendError: When the task to bring up the new ASG fails.
    """
    payload = {
        "name": cluster,
        "imageId": ami_id,
    }

    response = requests.post(NEW_ASG_URL,
            data=payload, params=ASGARD_API_TOKEN, timeout=REQUESTS_TIMEOUT)
    LOG.debug("Sent request to create new ASG in Cluster({}).".format(cluster))

    if response.status_code == 404:
        msg = "Can't create more ASGs for cluster {}. Please either wait " \
              "until older ASGs have been removed automatically or remove " \
              "old ASGs manually via Asgard."
        raise BackendError(msg.format(cluster))

    response = wait_for_task_completion(response.url, ASGARD_WAIT_TIMEOUT)
    if response['status'] == 'failed':
        msg = "Failure during new ASG creation. Task Log: \n{}".format(response['log'])
        raise BackendError(msg)

    # Potential Race condition if multiple people are making ASGs for the same cluster
    # Return the name of the newest asg
    new_asg = asgs_for_cluster(cluster)[-1]
    LOG.debug("New ASG({}) created in cluster({}).".format(new_asg, cluster))

    return new_asg


@retry()
def _get_asgard_resource_info(url):
    """
    A generic function for querying Asgard for inforamtion about a specific resource,
    such as an Autoscaling Group, A cluster.
    """

    LOG.debug("URL: {}".format(url))
    response = requests.get(url, params=ASGARD_API_TOKEN, timeout=REQUESTS_TIMEOUT)

    if response.status_code == 404:
        raise ResourceDoesNotExistException('Resource for url {} does not exist'.format(url))
    elif response.status_code >= 500:
        raise BackendError('Asgard experienced an error: {}'.format(response.text))
    elif response.status_code != 200:
        raise BackendError('Call to asgard failed with status code: {0}: {1}'
                           .format(response.status_code, response.text))

    LOG.debug("ASG info: {}".format(response.text))
    try:
        info = response.json()
    except ValueError as e:
        msg = "Could not parse resource info for {} as json.  Text: {}"
        raise BackendDataError(msg.format(url, response.text))
    return info


def get_asg_info(asg):
    """
    Queries Asgard for the status info on an ASG

    Arguments:
        asg(str): Name of the asg.

    Returns:
        dict: a Dictionary with the information about an ASG.

    Raises:
        TimeoutException: when the request for an ASG times out.
        BackendError: When a non 200 response code is returned from the Asgard API
        ASGDoesNotExistException: When an ASG does not exist
    """
    url = ASG_INFO_URL.format(asg)
    try:
        info = _get_asgard_resource_info(url)
    except ResourceDoesNotExistException as e:
        raise ASGDoesNotExistException('Autoscale group {} does not exist'.format(asg))

    return info


def get_cluster_info(cluster):
    """
    Queries Asgard for the status info of a cluster.

    Arguments:
        cluster(str): Name of the cluster.

    Returns:
        dict: a Dictionary with information about the asgard cluster.

    Raises:
        TimeoutException: when the request for an ASG times out.
        BackendError: When a non 200 response code is returned from the Asgard API
        ClusterDoesNotExistException: When an ASG does not exist
    """
    url = CLUSTER_INFO_URL.format(cluster)
    try:
        info = _get_asgard_resource_info(url)
    except ResourceDoesNotExistException as e:
        raise ClusterDoesNotExistException('Cluster {} does not exist'.format(cluster))

    return info


def is_asg_enabled(asg):
    """
    Checks to see if launching instances of an ASG is enabled.

    Argument:
        asg(str): ASG whose status should be checked.

    Returns:
        True if the asg status "launchingSuspended" is False, otherwise returns True
    """
    try:
        asgs = get_asg_info(asg)
    except ASGDoesNotExistException as e:
        # If an asg doesn't exist, it is not enabled.
        return False

    if asgs['group']['launchingSuspended'] is True:
        return False
    else:
        return True


def is_asg_pending_delete(asg):
    """
    Checks status of an ASG, specifically if it is pending deletion.

    Argument:
        asg(str): ASG whose status should be checked.

    Returns:
        True if the asg is in the "pending delete" status, else return False.

    Raises:
        TimeoutException: when the request for an ASG times out.
        BackendError: When a non 200 response code is returned from the Asgard API
        ASGDoesNotExistException: When an ASG does not exist
    """
    asgs = get_asg_info(asg)
    if asgs['group']['status'] is None:
        return False
    else:
        return True


def is_last_asg(asg):
    """
    Check to see if the given ASG is the last active ASG in its cluster.

    Argument:
        asg(str): The name of the ASG being checked.

    Returns:
        True if this is the last active ASG, else return False.

    Raises:
        TimeoutException: when the request for an ASG times out.
        BackendError: When a non 200 response code is returned from the Asgard API
        ASGDoesNotExistException: When an ASG does not exist

    """
    asg_info = get_asg_info(asg)
    cluster_name = asg_info['clusterName']
    cluster = get_cluster_info(cluster_name)

    if len(cluster) == 1: 
        return True

    return False


@retry()
def enable_asg(asg):
    """
    Enable an ASG in asgard.  This means it will have ELBs routing to it
    if any are associated and autoscaling will be turned on.

    Arguments:
        asg(str): The name of the asg to enable.

    Returns:
        None: When the asg has been enabled.

    Raises:
        TimeoutException: If the task to enable the ASG fails.
    """
    payload = { "name": asg }
    response = requests.post(ASG_ACTIVATE_URL,
            data=payload, params=ASGARD_API_TOKEN, timeout=REQUESTS_TIMEOUT)
    task_url = response.url
    task_status = wait_for_task_completion(task_url, 301)
    if task_status['status'] == 'failed':
        msg = "Failure while enabling ASG. Task Log: \n{}".format(task_status['log'])
        raise BackendError(msg)


@retry()
def disable_asg(asg):
    """
    Disable an ASG using asgard.
    curl -d "name=helloworld-example-v004" http://asgardprod/us-east-1/cluster/deactivate

    Arguments:
        asg(str): The name of the asg to disable.

    Returns:
        None: When the asg has been disabled.

    Raises:
        TimeoutException: If the task to enable the ASG fails..
        BackendError: If asgard was unable to disable the ASG
    """
    try:
        if is_asg_pending_delete(asg):
            LOG.info("Not disabling old ASG {} due to its pending deletion.".format(asg))
            return
    except ASGDoesNotExistException as e:
        LOG.info("Not disabling ASG {}, it no longer exists.".format(asg))
        return

    if is_last_asg(asg):
        msg = "Not disabling ASG {}, it is the last ASG in this cluster."
        raise CannotDisableActiveASG(msg)

    payload = { "name": asg }
    response = requests.post(ASG_DEACTIVATE_URL,
            data=payload, params=ASGARD_API_TOKEN, timeout=REQUESTS_TIMEOUT)
    task_url = response.url
    task_status = wait_for_task_completion(task_url, 300)
    if task_status['status'] == 'failed':
        msg = "Failure while disabling ASG. Task Log: \n{}".format(task_status['log'])
        raise BackendError(msg)


@retry()
def delete_asg(asg, fail_if_active=True, fail_if_last=True):
    """
    Delete an ASG using asgard.
    curl -d "name=helloworld-example-v004" http://asgardprod/us-east-1/cluster/delete

    Arguments:
        asg(str): The name of the asg to delete.

    Returns:
        None: When the asg has been deleted.

    Raises:
        TimeoutException: If the task to delete the ASG fails...
        BackendError: If asgard was unable to delete the ASG
        ASGDoesNotExistException: When an ASG does not exist
    """
    if is_asg_pending_delete(asg):
        LOG.info("Not deleting ASG {} due to its already pending deletion.".format(asg))
        return
    if fail_if_active and is_asg_enabled(asg):
        msg = "Not deleting ASG {} as it is currently active.".format(asg)
        LOG.warn(msg)
        raise CannotDeleteActiveASG(msg)

    if fail_if_last and is_last_asg(asg):
        msg = "Not deleting ASG {} since it is the last ASG in this cluster."
        LOG.warn(msg)
        raise CannotDeleteLastASG(msg)

    payload = {"name": asg}
    response = requests.post(ASG_DELETE_URL,
                             data=payload, params=ASGARD_API_TOKEN, timeout=REQUESTS_TIMEOUT)
    task_url = response.url
    task_status = wait_for_task_completion(task_url, 300)
    if task_status['status'] == 'failed':
        msg = "Failure while deleting ASG. Task Log: \n{}".format(task_status['log'])
        raise BackendError(msg)


@retry()
def elbs_for_asg(asg):
    response = requests.get(ASG_INFO_URL.format(asg),
        params=ASGARD_API_TOKEN, timeout=REQUESTS_TIMEOUT)
    try:
        resp_json = response.json()
        elbs = resp_json['group']['loadBalancerNames']
    except (KeyError, TypeError) as e:
        msg = "Expected a dict with path ['group']['loadbalancerNames']. " \
            "Got: {}".format(resp_json)
        raise BackendDataError(msg)
    return elbs


def deploy(ami_id):
    """
    Deploys an AMI to AWS EC2

    Arguments:
        ami_id(str): AWS AMI ID

    Returns:
        dict(str, [str]): Returns a dictionary with the keys: 'current_asgs' and 'disabled_asgs'

    Raises:
        TimeoutException: When the task to bring up the new instance times out.
        BackendError: When the task to bring up the new instance fails.
        ASGDoesNotExistException: If the ASG being queried does not exist.
    """
    LOG.info( "Processing request to deploy {}.".format(ami_id))

    # Pull the EDP from the AMI ID
    edp = ec2.edp_for_ami(ami_id)

    # These are all autoscaling groups that match the tags we care about.
    asgs = ec2.asgs_for_edp(edp, filter_asgs_pending_delete=False)

    # All the ASGs except for the new one
    # we are about to make.
    existing_clusters = clusters_for_asgs(asgs)
    LOG.info("Deploying to {}".format(existing_clusters.keys()))

    new_asgs = {}
    for cluster in existing_clusters.keys():
        try:
            new_asgs[cluster] = new_asg(cluster, ami_id)
        except:
            msg = "Failed to create new asg for {} but did make asgs for {}"
            msg = msg.format(cluster, new_asgs.keys())
            LOG.error(msg)
            raise

    LOG.info("New ASGs: {}".format(new_asgs.values()))
    ec2.wait_for_in_service(new_asgs.values(), 300)
    LOG.info("ASG instances are healthy. Enabling Traffic.")

    elbs_to_monitor = []
    current_asgs = defaultdict(list)  # Used to store the return value of what ASG's are currently deployed
    for cluster, asg in new_asgs.iteritems():
        try:
            enable_asg(asg)
            elbs_to_monitor.extend(elbs_for_asg(asg))
            current_asgs['cluster'].append(asg)
        except:
            LOG.error("Something went wrong with {}, disabling traffic.".format(asg))
            LOG.error(traceback.format_exc())
            disable_asg(asg)
            # Also disable any new ASGs that may already be enabled
            for _, asg_list in current_asgs:
                for asg_to_disable in asg_list:
                    try:
                        disable_asg(asg_to_disable)
                    except:
                        continue
            raise

    LOG.info("All new ASGs are active.  The new instances "
          "will be available when they pass the healthchecks.")
    LOG.info("New ASGs: {}".format(new_asgs.values()))

    # Wait for all instances to be in service in all ELBs
    try:
        ec2.wait_for_healthy_elbs(elbs_to_monitor, 600)
    except:
        LOG.info(" Some instances are failing ELB health checks. "
              "Pulling out the new ASG.")
        for cluster, asg in new_asgs.iteritems():
            disable_asg(asg)
        raise

    LOG.info("New instances have succeeded in passing the healthchecks. "
          "Disabling old ASGs.")
    # ensure the new ASG is still healthy and not pending delete before disabling the old ASGs
    for cluster, asg in new_asgs.iteritems():
        if is_asg_pending_delete(asg) or not is_asg_enabled(asg):
            raise BackendError("New Autoscale Group {} is pending delete, Aborting the disabling of old ASGs.".format(asg))

    disabled_asg = defaultdict(list)
    for cluster,asgs in existing_clusters.iteritems():
        for asg in asgs:
            if is_asg_enabled(asg):
                disable_asg(asg)
                disabled_asg[cluster].append(asg)
            try:
                ec2.tag_asg_for_deletion(asg)
            except ASGDoesNotExistException as e:
                LOG.info("Unable to tag ASG {} as it no longer exists, skipping".format(asg))

    LOG.info("Woot! Deploy Done!")
    return {'current_asgs': current_asgs, 'disabled_asgs': disabled_asg}
