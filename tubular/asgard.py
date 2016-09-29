from datetime import datetime,timedelta
import os
import logging
import requests
import time
import traceback
import copy
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
from utils import WAIT_SLEEP_TIME, DISABLE_OLD_ASG_WAIT_TIME

ASGARD_API_ENDPOINT = os.environ.get("ASGARD_API_ENDPOINTS", "http://dummy.url:8091/us-east-1")
ASGARD_API_TOKEN = "asgardApiToken={}".format(os.environ.get("ASGARD_API_TOKEN", "dummy-token"))
ASGARD_WAIT_TIMEOUT = int(os.environ.get("ASGARD_WAIT_TIMEOUT", 600))
ASGARD_ELB_HEALTH_TIMEOUT = int(os.environ.get("ASGARD_ELB_HEALTH_TIMEOUT", 600))
REQUESTS_TIMEOUT = float(os.environ.get("REQUESTS_TIMEOUT", 10))

CLUSTER_LIST_URL= "{}/cluster/list.json".format(ASGARD_API_ENDPOINT)
ASG_ACTIVATE_URL= "{}/cluster/activate".format(ASGARD_API_ENDPOINT)
ASG_DEACTIVATE_URL= "{}/cluster/deactivate".format(ASGARD_API_ENDPOINT)
ASG_DELETE_URL= "{}/cluster/delete".format(ASGARD_API_ENDPOINT)
NEW_ASG_URL= "{}/cluster/createNextGroup".format(ASGARD_API_ENDPOINT)
ASG_INFO_URL="{}/autoScaling/show/{}.json".format(ASGARD_API_ENDPOINT, "{}")
CLUSTER_INFO_URL = "{}/cluster/show/{}.json".format(ASGARD_API_ENDPOINT, "{}")

LOG = logging.getLogger(__name__)


def _parse_json(url, response):
    """
    Protect against non-JSON responses that are sometimes returned from Asgard.
    """
    try:
        response_json = response.json()
    except ValueError as e:
        msg = "Expected json response from url: '{}' - but got the following:\n{}"
        raise BackendError(msg.format(url, response.text))
    return response_json


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
    cluster_json = _parse_json(url, response)

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
    asgs = _parse_json(url, response)

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
        json_response = _parse_json(task_url, response)
        if json_response['status'] in ('completed', 'failed'):
            return json_response

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
    return _parse_json(url, response)


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

    return not asgs['group']['launchingSuspended']


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
    url = ASG_INFO_URL.format(asg)
    response = requests.get(url, params=ASGARD_API_TOKEN, timeout=REQUESTS_TIMEOUT)
    resp_json = _parse_json(url, response)
    try:
        elbs = resp_json['group']['loadBalancerNames']
    except (KeyError, TypeError) as e:
        msg = "Expected a dict with path ['group']['loadbalancerNames']. " \
            "Got: {}".format(resp_json)
        raise BackendDataError(msg)
    return elbs

def rollback(current_clustered_asgs, rollback_to_clustered_asgs, ami_id=None):
    """
    Rollback to a particular list of ASGs for one or more clusters.
    If rollback does not succeed, create new ASGs based on the AMI ID and deploy those ASGs.

    Arguments:
        current_clustered_asgs(dict): ASGs currently enabled, grouped by cluster.
        rollback_to_clustered_asgs(dict): ASGs to rollback to, grouped by cluster.
        ami_id(str): AWS AMI ID to which to rollback to.

    Returns:
        dict(str, str, dict): Returns a dictionary with the keys:
            'ami_id' - AMI id used to deploy the AMI, None if unspecified
            'current_asgs' - Lists of current active ASGs, keyed by cluster.
            'disabled_asgs' - Lists of current inactive ASGs, keyed by cluster.

    Raises:
        TimeoutException: When the task to bring up the new instance times out.
        BackendError: When the task to bring up the new instance fails.
        ASGDoesNotExistException: If the ASG being queried does not exist.
    """
    # First, ensure that the ASGs to which we'll rollback are not tagged for deletion.
    # Also, ensure that those same ASGs are not in the process of deletion.
    rollback_ready = True
    asgs_tagged_for_deletion = [asg.name for asg in ec2.get_asgs_pending_delete()]
    for cluster, asgs in rollback_to_clustered_asgs.iteritems():
        for asg in asgs:
            err_msg = None
            if asg in asgs_tagged_for_deletion:
                # ASG is tagged for deletion. Remove the deletion tag.
                ec2.remove_asg_deletion_tag(asg)
            if is_asg_pending_delete(asg):
                # Too late for rollback - this ASG is already pending delete.
                LOG.info("Rollback ASG '{}' is pending delete. Aborting rollback to ASGs.".format(asg))
                rollback_ready = False
                break

    if rollback_ready:
        # Perform the rollback.
        success, enabled_asgs, disabled_asgs = _red_black_deploy(rollback_to_clustered_asgs, current_clustered_asgs)
        if not success:
            LOG.info("Rollback failed for cluster(s) {}.".format(current_clustered_asgs.keys()))
        else:
            LOG.info("Woot! Rollback Done!")
            return {'ami_id': ami_id, 'current_asgs': enabled_asgs, 'disabled_asgs': disabled_asgs }

    # Rollback failed -or- wasn't attempted. Attempt a deploy.
    if ami_id:
        LOG.info("Attempting rollback via deploy of AMI {}.".format(ami_id))
        return deploy(ami_id)
    else:
        LOG.info("No AMI id specified - so no deploy occurred during rollback.")
        return {'ami_id': None, 'current_asgs': current_clustered_asgs, 'disabled_asgs': rollback_to_clustered_asgs}

def deploy(ami_id):
    """
    Deploys an AMI as an auto-scaling group (ASG) to AWS.

    Arguments:
        ami_id(str): AWS AMI ID

    Returns:
        dict(str, str, dict): Returns a dictionary with the keys:
            'ami_id' - AMI id used to deploy the AMI
            'current_asgs' - Lists of current active ASGs, keyed by cluster.
            'disabled_asgs' - Lists of current inactive ASGs, keyed by cluster.

    Raises:
        TimeoutException: When the task to bring up the new instance times out.
        BackendError: When the task to bring up the new instance fails.
        ASGDoesNotExistException: If the ASG being queried does not exist.
    """
    LOG.info( "Processing request to deploy {}.".format(ami_id))

    # Pull the EDP from the AMI ID
    edp = ec2.edp_for_ami(ami_id)

    # These are all autoscaling groups that match the tags we care about.
    existing_edp_asgs = ec2.asgs_for_edp(edp, filter_asgs_pending_delete=False)

    # Find the clusters for all the existing ASGs.
    existing_clustered_asgs = clusters_for_asgs(existing_edp_asgs)
    LOG.info("Deploying to cluster(s) {}".format(existing_clustered_asgs.keys()))

    # Create a new ASG in each cluster.
    new_clustered_asgs = defaultdict(list)
    for cluster in existing_clustered_asgs.keys():
        try:
            new_clustered_asgs[cluster].append(new_asg(cluster, ami_id))
        except:
            msg = "ASG creation failed for cluster {} but succeeded for cluster(s) {}."
            msg = msg.format(cluster, new_clustered_asgs.keys())
            LOG.error(msg)
            raise

    new_asgs = [asgs[0] for asgs in new_clustered_asgs.values()]
    LOG.info("New ASGs created: {}".format(new_asgs))
    ec2.wait_for_in_service(new_asgs, 300)
    LOG.info("New ASGs healthy: {}".format(new_asgs))

    LOG.info("Enabling traffic to new ASGs for the {} cluster(s).".format(existing_clustered_asgs.keys()))
    success, enabled_asgs, disabled_asgs = _red_black_deploy(dict(new_clustered_asgs), existing_clustered_asgs)
    if not success:
        raise BackendError("Error performing red/black deploy - deploy was unsuccessful. "
                           "enabled_asgs: {} - disabled_asgs: {}".format(enabled_asgs, disabled_asgs))

    LOG.info("Woot! Deploy Done!")
    return {'ami_id': ami_id, 'current_asgs': enabled_asgs, 'disabled_asgs': disabled_asgs}

def _red_black_deploy(
    new_cluster_asgs, baseline_cluster_asgs,
    secs_before_old_asgs_disabled=DISABLE_OLD_ASG_WAIT_TIME
):
    """
    Takes two dicts of autoscale groups, new and baseline.
    Each dict key is a cluster name.
    Each dict value is a list of ASGs for that cluster.
    Enables the new ASGs, then disables the old ASGs.

    Red/black deploy refers to:
        - Existing ASG is "red", meaning active.
        - New ASG begins as "black", meaning inactive.
        - The new ASG is added to the ELB, making it "red".
            - The baseline and new ASGs are now existing as "red/red".
        - The baseline ASG is removed from the ELB.
            - As traffic has ceased to be directed to the baseline ASG, it becomes "black".

    Workflow:
        - enable new ASGs
        - wait for instances to be healthy in the load balancer
        - ensure the new ASGs are not pending delete or disabled
        - tag and disable current asgs

    Args:
        new_asgs (dict): List of new ASGs to be added to the ELB, keyed by cluster.
        baseline_asgs (dict): List of existing ASGs already added to the ELB, keyed by cluster.

    Returns:
        success (bool): True if red/black operation succeeded, else False.
        asgs_enabled (dict): List of ASGs that are added to the ELB, keyed by cluster.
        asgs_disabled (dict): List of ASGs that are removed from the ELB, keyed by cluster.
    """
    asgs_enabled = copy.deepcopy(baseline_cluster_asgs)
    asgs_disabled = copy.deepcopy(new_cluster_asgs)

    def enable_cluster_asg(cluster, asg):
        """
        Shifts ASG from disabled to enabled.
        """
        enable_asg(asg)
        asgs_disabled[cluster].remove(asg)
        asgs_enabled[cluster].append(asg)

    def disable_cluster_asg(cluster, asg):
        """
        Shifts ASG from enabled to disabled.
        """
        disable_asg(asg)
        asgs_enabled[cluster].remove(asg)
        asgs_disabled[cluster].append(asg)

    def disable_clustered_asgs(clustered_asgs, failure_msg):
        """
        Disable all the ASGs in the lists, keyed by cluster.
        """
        for cluster, asgs in clustered_asgs.iteritems():
            for asg in asgs:
                try:
                    disable_cluster_asg(cluster, asg)
                except:
                    LOG.warning(failure_msg.format(asg))

    elbs_to_monitor = []
    newly_enabled_asgs = defaultdict(list)
    for cluster, asgs in new_cluster_asgs.iteritems():
        for asg in asgs:
            try:
                enable_cluster_asg(cluster, asg)
                elbs_to_monitor.extend(elbs_for_asg(asg))
                newly_enabled_asgs[cluster].append(asg)
            except Exception:
                LOG.error("Error enabling ASG '{}'. Disabling traffic to all new ASGs.".format(asg))
                LOG.error(traceback.format_exc())
                # Disable the ASG which failed first.
                disable_cluster_asg(cluster, asg)
                # Then disable any new other ASGs that have been newly enabled.
                disable_clustered_asgs(
                    newly_enabled_asgs,
                    "Unable to disable ASG '{}' after failure."
                )
                return (False, asgs_enabled, asgs_disabled)

    LOG.info("New ASGs {} are active and will be available after passing the healthchecks.".format(
        dict(newly_enabled_asgs)
    ))

    # Wait for all instances to be in service in all ELBs.
    try:
        ec2.wait_for_healthy_elbs(elbs_to_monitor, 600)
    except Exception as wait_fail:
        LOG.info("Some ASGs are failing ELB health checks. Disabling traffic to all new ASGs.")
        disable_clustered_asgs(
            newly_enabled_asgs,
            "Unable to disable ASG '{}' after waiting for healthy ELBs."
        )
        return (False, asgs_enabled, asgs_disabled)

    # Add a sleep delay here to wait and see how the new ASGs react to traffic.
    # A flawed release would likely make the new ASGs fail the health checks below
    # and, if any new ASGs fail the health checks, the old ASGs would *not be disabled.
    time.sleep(secs_before_old_asgs_disabled)

    # Ensure the new ASGs are still healthy and not pending delete before disabling the old ASGs.
    for cluster, asgs in newly_enabled_asgs.iteritems():
        for asg in asgs:
            err_msg = None
            if is_asg_pending_delete(asg):
                err_msg = "New ASG '{}' is pending delete.".format(asg)
            elif not is_asg_enabled(asg):
                err_msg = "New ASG '{}' is not enabled.".format(asg)
            if err_msg:
                LOG.error("{} Aborting disabling of old ASGs.".format(err_msg))
                return (False, asgs_enabled, asgs_disabled)

    LOG.info("New ASGs have passed the healthchecks. Now disabling old ASGs.")

    for cluster, asgs in baseline_cluster_asgs.iteritems():
        for asg in asgs:
            if is_asg_enabled(asg):
                try:
                    disable_cluster_asg(cluster, asg)
                except:
                    LOG.warning("Unable to disable ASG '{}' after enabling new ASGs.".format(asg))
            try:
                ec2.tag_asg_for_deletion(asg)
            except ASGDoesNotExistException as e:
                LOG.info("Unable to tag ASG '{}' as it no longer exists, skipping.".format(asg))

    return (True, asgs_enabled, asgs_disabled)
