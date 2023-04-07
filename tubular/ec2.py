"""
Convenience functions built on top of boto that are useful
when we deploy using asgard.
"""

import os
import logging
import time
from datetime import datetime, timedelta, timezone
import backoff
import boto3
import boto
from boto.exception import EC2ResponseError
from boto3.exceptions import Boto3Error
from botocore.exceptions import HTTPClientError
from botocore.exceptions import OperationNotPageableError


from boto.ec2.autoscale.tag import Tag
from tubular.utils import EDP, WAIT_SLEEP_TIME
from tubular.exception import (
    ImageNotFoundException,
    MultipleImagesFoundException,
    MissingTagException,
    TimeoutException,
    HTTPClientError
)

LOG = logging.getLogger(__name__)

ISO_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
ASG_DELETE_TAG_KEY = 'delete_on_ts'
MAX_ATTEMPTS = int(os.environ.get('RETRY_MAX_ATTEMPTS', 5))
RETRY_FACTOR = os.environ.get('RETRY_FACTOR', 1.5)


def giveup_if_not_throttling(ex):
    """
    Checks that a Boto3Error exceptions message contains the throttling string.

    Args:
        ex (boto.exception.Boto3Error):

    Returns:
        False if the throttling string is not found.
        True if ex is of type MultipleImagesFoundException
    """

    if 'throttling' not in str(ex).lower():
        return False
    elif ex.response['Error']['Code'] == 'MultipleImagesFoundException':
        return True

    return not False


@backoff.on_exception(backoff.expo,
                      Boto3Error,
                      max_tries=MAX_ATTEMPTS,
                      giveup=giveup_if_not_throttling,
                      factor=RETRY_FACTOR)
def get_all_autoscale_groups(names=None):
    """
    Get all the autoscale groups

    Arguments:
        names (list) - A list of ASG names as strings
    Returns:
        List of :class:`boto.ec2.autoscale.group.AutoScalingGroup` instances.
    """
    autoscale_client = boto3.client('autoscaling')
    asg_paginator = autoscale_client.get_paginator('describe_auto_scaling_groups')

    total_asgs = []
    if names is None:
        paginator = asg_paginator.paginate()
    else:
        paginator = asg_paginator.paginate(AutoScalingGroupNames=names)
    for asg_page in paginator:
        total_asgs.extend(asg_page['AutoScalingGroups'])

    return total_asgs


@backoff.on_exception(backoff.expo,
                      Boto3Error,
                      max_tries=MAX_ATTEMPTS,
                      giveup=giveup_if_not_throttling,
                      factor=RETRY_FACTOR)
def get_all_load_balancers(names=None):
    """
    Get all the ELBs

    Arguments:
        names (list): A list of ELB names as strings

    Returns:
        a list of :class:`boto.ec2.elb.loadbalancer.LoadBalancer`
    """
    client = boto3.client('elb')
    paginator = client.get_paginator('describe_load_balancers')

    if names:
        response_iterator = paginator.paginate(LoadBalancerNames=names)
    else:
        response_iterator = paginator.paginate()

    total_elbs = []

    if response_iterator is not None:
        try:
            for page in response_iterator:
                if 'LoadBalancerDescriptions' in page:
                    total_elbs.extend(page['LoadBalancerDescriptions'])
        except Exception as e:
            raise Exception("Unexpected error in check_pagination: " + e.__str__())

    return total_elbs


def _instance_elbs(instance_id, elbs):
    """
    Given an EC2 instance and ELBs, return the ELB(s) in which it is active.

    Arguments:
        instance_id (:obj:`boto.ec2.instance.Reservation`): Instance used to find out which ELB it is active in.
        elbs (:obj:`list` of :obj:`boto.ec2.elb.loadbalancer.LoadBalancer`): List of ELBs to us in checking.
    Returns:
        :obj:`list` of :obj:`boto.ec2.elb.loadbalancer.LoadBalancer`:
                One or more ELBs used by the passed-in instance -or- None.
    """
    instance_elbs = []
    for elb in elbs:
        elb_instance_ids = [inst.id for inst in elb.instances]
        if instance_id in elb_instance_ids:
            instance_elbs.append(elb)
    return instance_elbs


@backoff.on_exception(backoff.expo,
                      OperationNotPageableError,
                      max_tries=MAX_ATTEMPTS,
                      giveup=giveup_if_not_throttling,
                      factor=RETRY_FACTOR)
def active_ami_for_edp(env, dep, play):
    """
    Given an environment, deployment, and play, find the base AMI id used for the active deployment.

    Arguments:
        env (str): Environment to check (stage, prod, loadtest, etc.)
        dep (str): Deployment to check (edx, edge, mckinsey, etc.)
        play (str): Play to check (edxapp, discovery, ecommerce, etc.)
    Returns:
        str: Base AMI id of current active deployment for the EDP.
    Raises:
        MultipleImagesFoundException: If multiple AMI IDs are found within the EDP's ELB.
        ImageNotFoundException: If no AMI IDs are found for the EDP.
    """

    LOG.info("Looking up AMI for {}-{}-{}...".format(env, dep, play))
    edp = EDP(env, dep, play)
    #ec2_conn = boto.connect_ec2()
    ec2_client = boto3.client('ec2')
    asg_client = boto3.client('autoscaling')

    all_elbs = get_all_load_balancers()
    LOG.info("Found {} load balancers.".format(len(all_elbs)))
    edp_filter = {
        "tag:environment": env,
        "tag:deployment": dep,
        "tag:play": play,
    }
    edp_filter_env = {
        "Name": "tag:environment",
        "Values": [env]
    }
    edp_filter_deployment = {
        "Name": "tag:deployment",
        "Values": [dep]
    }
    edp_filter_play = {
        "Name": "tag:play",
        "Values": [play]
    }
    amis = set()
    instances_by_id = {}
    ec2 = boto3.resource('ec2')
    instances = ec2.instances.filter(Filters=[edp_filter_env, edp_filter_deployment, edp_filter_play])
    #LOG.info("{} reservations found for EDP {}-{}-{}".format(len(instances), env, dep, play))

    for instance in instances:
        # Need to build up instances_by_id for code below
        instances_by_id[instance.id] = instance

    asgs = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=asgs_for_edp(edp))

    for asg in asgs['AutoScalingGroups']:
        for asg_inst in asg['Instances']:
            asg_enabled = len(asg['SuspendedProcesses']) == 0
            if asg_inst['LifecycleState'] == "InService" and asg_enabled:
                amis.add(asg_inst['InstanceId'])
                LOG.info("AMI found in ASG {} for {}-{}-{}: {}".format(asg['AutoScalingGroupName'], env, dep, play, asg_inst['InstanceId']))
            else:
                LOG.info("Instance {} state: {} - asg {} enabled: {}".format(
                    asg_inst['InstanceId']['InstanceId'], asg_inst['LifecycleState'], asg['AutoScalingGroupName'], asg_enabled))

    if not amis:
        msg = "No AMIs found for {}-{}-{}.".format(env, dep, play)
        raise ImageNotFoundException(msg)

    return amis.pop()


@backoff.on_exception(backoff.expo,
                      Boto3Error,
                      max_tries=MAX_ATTEMPTS,
                      giveup=giveup_if_not_throttling,
                      factor=RETRY_FACTOR)
def tags_for_ami(ami_id):
    """
    Look up the tags for an AMI.

    Arguments:
        ami_id (str): An AMI Id.
    Returns:
        dict: The tags for this AMI.
    Raises:
        ImageNotFoundException: No image found with this ami ID.
        MissingTagException: AMI is missing one or more of the expected tags.
    """

    LOG.debug("Looking up edp for {}".format(ami_id))
    ec2 = boto3.client('ec2', region_name='us-east-1')
    try:
        resp = ec2.describe_images(ImageIds=[ami_id])
        ami = resp['Images']
    except IndexError:
        raise ImageNotFoundException("ami: {} not found".format(ami_id))
    except EC2ResponseError as error:
        raise ImageNotFoundException(str(error))

    return ami[0]['Tags']


def edp_for_ami(ami_id):
    """
    Look up the EDP tags for an AMI.

    Arguments:
        ami_id (str): An AMI Id.
    Returns:
        EDP Named Tuple: The EDP tags for this AMI.
    Raises:
        ImageNotFoundException: No image found with this ami ID.
        MissingTagException: AMI is missing one or more of the expected tags.
    """

    tags = tags_for_ami(ami_id)

    try:
        edp = EDP(tags[0]['Value'], tags[1]['Value'], tags[2]['Value'])
    except (KeyError, IndexError) as key_err:
        missing_key = key_err.args[0]
        msg = "{} is missing the {} tag.".format(ami_id, missing_key)
        raise MissingTagException(msg)

    LOG.debug("Got EDP for {}: {}".format(ami_id, edp))
    return edp


def validate_edp(ami_id, environment, deployment, play):
    """
    Validate that an AMI is tagged for a specific EDP (environment, deployment, play).

    Arguments:
        ami_id (str): An AMI Id.
        environment (str): Environment for AMI, e.g. prod, stage
        deployment (str): Deployment for AMI, e.g. edx, edge
        play (str): Play for AMI, e.g. edxapp, insights, discovery
    Returns:
        True if AMI EDP matches specified EDP, otherwise False.
    """
    edp = edp_for_ami(ami_id)
    edp_matched = (edp.environment == environment and
                   edp.deployment == deployment and
                   edp.play == play)
    if not edp_matched:
        LOG.info("AMI {0} EDP did not match specified: {1} != ({2}, {3}, {4})".format(
            ami_id, edp, environment, deployment, play
        ))
    return edp_matched


def is_stage_ami(ami_id):
    """
    Check if an AMI is intended for stage deployment.

    Arguments:
        ami_id (str): An AMI Id.
    Returns:
        True if AMI environment is "stage", otherwise False.
    """
    edp = edp_for_ami(ami_id)
    ami_for_stage = edp.environment == "stage"
    if not ami_for_stage:
        LOG.info("AMI {0} is not intended for stage! - {1}".format(ami_id, edp))
    return ami_for_stage


def asgs_for_edp(edp, filter_asgs_pending_delete=True):
    """
    All AutoScalingGroups that have the tags of this play.

    A play is made up of many auto_scaling groups.

    Arguments:
        EDP Named Tuple: The edp tags for the ASGs you want.
    Returns:
        list: list of ASG names that match the EDP.
    eg.

     [
         u'edxapp-v018',
         u'sandbox-edx-hacking-ASG',
         u'sandbox-edx-insights-ASG',
         u'test-edx-ecomapp',
         u'test-edx-edxapp-v007',
         u'test2-edx-certificates',
     ]

    """

    all_groups = get_all_autoscale_groups()
    matching_groups = []
    LOG.info("Found {} ASGs".format(len(all_groups)))

    for group in all_groups:
        LOG.debug("Checking group {}".format(group))
        tags = {tag['Key']: tag['Value'] for tag in group['Tags']}
        LOG.debug("Tags for asg {}: {}".format(group['AutoScalingGroupName'], tags))
        if filter_asgs_pending_delete and ASG_DELETE_TAG_KEY in tags.keys():
            LOG.info("filtering ASG: {0} because it is tagged for deletion on: {1}"
                     .format(group['AutoScalingGroupName'], tags[ASG_DELETE_TAG_KEY]))
            continue

        edp_keys = ['environment', 'deployment', 'play']
        if all([tag in tags for tag in edp_keys]):
            group_env = tags['environment']
            group_deployment = tags['deployment']
            group_play = tags['play']

            group_edp = EDP(group_env, group_deployment, group_play)

            if group_edp == edp:
                matching_groups.append(group['AutoScalingGroupName'])

    LOG.info(
        "Returning %s ASGs for EDP %s-%s-%s.",
        len(matching_groups),
        edp.environment,
        edp.deployment,
        edp.play
    )
    return matching_groups


def create_tag_for_asg_deletion(asg_name, seconds_until_delete_delta=None):
    """
    Create a tag that will be used to mark an ASG for deletion.
    """
    if seconds_until_delete_delta is None:
        tag_value = None
    else:
        tag_value = (datetime.utcnow() + timedelta(seconds=seconds_until_delete_delta)).isoformat()
    tag = {
        'Key': ASG_DELETE_TAG_KEY,
        'Value': tag_value,
        'PropagateAtLaunch': False,
        'ResourceId': asg_name,
        'ResourceType': 'auto-scaling-group',
    }

    return tag


@backoff.on_exception(backoff.expo,
                      Boto3Error,
                      max_tries=MAX_ATTEMPTS,
                      giveup=giveup_if_not_throttling,
                      factor=RETRY_FACTOR)
def tag_asg_for_deletion(asg_name, seconds_until_delete_delta=600):
    """
    Tag an asg with a tag named ASG_DELETE_TAG_KEY with a value of the MS since epoch UTC + ms_until_delete_delta
    that an ASG may be deleted.

    Arguments:
        asg_name (str): the name of the autoscale group to tag

    Returns:
        None
    """
    tag = create_tag_for_asg_deletion(asg_name, seconds_until_delete_delta)

    autoscale = boto3.client('autoscaling')
    if len(get_all_autoscale_groups([asg_name])) < 1:
        LOG.info("ASG {} no longer exists, will not tag".format(asg_name))
    else:
        autoscale.create_or_update_tags(Tags=[tag])


@backoff.on_exception(backoff.expo,
                      Boto3Error,
                      max_tries=MAX_ATTEMPTS,
                      giveup=giveup_if_not_throttling,
                      factor=RETRY_FACTOR)
def remove_asg_deletion_tag(asg_name):
    """
    Remove deletion tag from an asg.

    Arguments:
        asg_name (str): the name of the autoscale group from which to remove the deletion tag

    Returns:
        None
    """
    asgs = get_all_autoscale_groups([asg_name])
    if len(asgs) < 1:
        LOG.info("ASG {} no longer exists, will not remove deletion tag.".format(asg_name))
    else:
        for asg in asgs:
            for tag in asg['Tags']:
                if tag['Key'] == ASG_DELETE_TAG_KEY:
                    tag.delete()


def get_asgs_pending_delete():
    """
    Get a list of all the autoscale groups marked with the ASG_DELETE_TAG_KEY.
    Return only those groups who's ASG_DELETE_TAG_KEY as past the current time.

    It's intended for this method to be robust and to return as many ASGs that
    are pending delete as possible even if an error occurs during the process.

    Returns:
        List(<boto.ec2.autoscale.group.AutoScalingGroup>)
    """
    current_datetime = datetime.utcnow()

    asgs_pending_delete = []
    asgs = get_all_autoscale_groups()
    LOG.debug("Found {0} autoscale groups".format(len(asgs)))
    for asg in asgs:
        LOG.debug("Checking for {0} on asg: {1}".format(ASG_DELETE_TAG_KEY, asg['AutoScalingGroupName']))
        for tag in asg['Tags']:
            try:
                if tag['Key'] == ASG_DELETE_TAG_KEY:
                    LOG.debug("Found {0} tag, deletion time: {1}".format(ASG_DELETE_TAG_KEY, tag['Value']))
                    if datetime.strptime(tag['Value'], ISO_DATE_FORMAT) - current_datetime < timedelta(0, 0, 0):
                        LOG.debug("Adding ASG: {0} to the list of ASGs to delete.".format(asg['AutoScalingGroupName']))
                        asgs_pending_delete.append(asg)
                        break
            except ValueError:
                LOG.warning(
                    "ASG {0} has an improperly formatted datetime string for the key {1}. Value: {2} . "
                    "Format must match {3}".format(
                        asg['AutoScalingGroupName'], tag['Key'], tag['Value'], ISO_DATE_FORMAT
                    )
                )
                continue
            except Exception as err:  # pylint: disable=broad-except
                LOG.warning("Error occured while building a list of ASGs to delete, continuing: {0}".format(err))
                continue

    LOG.info("Number of ASGs pending delete: {0}".format(len(asgs_pending_delete)))
    return asgs_pending_delete


def terminate_instances(region, tags, max_run_hours, skip_if_tag):
    """
    Terminates instances based on tag and the number of hours an instance has been running.

    Args:
        region (str): the ec2 region to search for instances.
        tags (dict): tag names/values to search for instances (e.g. {'tag:Name':'*string*'} ).
        max_run_hours (int): number of hours the instance should be left running before termination.
        skip_if_tag (str): Instance will not be terminated if it is tagged with this value.

    Returns:
        list: of the instance IDs terminated.
    """
    conn = boto3.client('ec2')
    instances_to_terminate = []

    reservations = conn.describe_instances(Filters=[tags])

    for reservation in reservations['Reservations']:
        for instance in reservation['Instances']:
            launch_time = instance['LaunchTime']
            total_run_time = datetime.utcnow() - datetime.strptime(launch_time.strftime(ISO_DATE_FORMAT), ISO_DATE_FORMAT)
            if total_run_time > timedelta(hours=max_run_hours) and skip_if_tag not in [tag['Key'] for tag in instance['Tags']]:
                instances_to_terminate.append(instance['InstanceId'])

    if instances_to_terminate:
        conn.terminate_instances(InstanceIds=instances_to_terminate)

    return instances_to_terminate


def wait_for_in_service(all_asgs, timeout):
    """
    Wait for the ASG and all instances in them to be healthy
    according to AWS metrics.

    Arguments:
        all_asgs(list<str>): A list of ASGs we want to be healthy.
        timeout: The amount of time in seconds to wait for healthy state.
    [
        u'test-edx-edxapp-v008',
        u'test-edx-worker-v005',
    ]

    Returns: Nothing if healthy, raises a timeout exception if un-healthy.
    """
    if not all_asgs:
        LOG.info("No ASGs to monitor - skipping health check.")
        return

    asgs_left_to_check = list(all_asgs)
    LOG.info("Waiting for ASGs to be healthy: {}".format(asgs_left_to_check))

    end_time = datetime.utcnow() + timedelta(seconds=timeout)
    while end_time > datetime.utcnow():
        asgs = get_all_autoscale_groups(asgs_left_to_check)
        for asg in asgs:
            all_healthy = True
            for instance in asg['Instances']:
                if instance['HealthStatus'].lower() != 'healthy' or instance['LifecycleState'].lower() != 'inservice':
                    # Instance is not ready.
                    all_healthy = False
                    break

            if all_healthy:
                # Then all are healthy we can stop checking this.
                LOG.debug("All instances healthy in ASG: {}".format(asg['AutoScalingGroupName']))
                LOG.debug(asgs_left_to_check)
                asgs_left_to_check.remove(asg['AutoScalingGroupName'])

        if not asgs_left_to_check:
            return

        time.sleep(1)

    raise TimeoutException("Some instances in the following ASGs never became healthy: {}".format(asgs_left_to_check))


def wait_for_healthy_elbs(elbs_to_monitor, timeout):
    """
    Wait for all instances in all ELBs listed to be healthy. Raise a
    timeout exception if they don't become healthy.

    Arguments:
        elbs_to_monitor(list<str>): Names of ELBs that we are monitoring.
        timeout: Timeout in seconds of how long to wait.

    Returns:
        None: When all ELBs have only healthy instances in them.

    Raises:
        TimeoutException: We we have run out of time.
    """
    client = boto3.client('elb')

    @backoff.on_exception(backoff.expo,
                          Boto3Error,
                          max_tries=MAX_ATTEMPTS,
                          giveup=giveup_if_not_throttling,
                          factor=RETRY_FACTOR)
    def _get_elb_health(selected_elb):
        """
        Get the health of an ELB

        Args:
            selected_elb str name of the elb

        Returns:
            list of
        {
            'InstanceId': 'string',
            'State': 'string',
            'ReasonCode': 'string',
            'Description': 'string'
        },

        """
        response = client.describe_instance_health(LoadBalancerName=selected_elb)
        return response['InstanceStates']

    if not elbs_to_monitor:
        LOG.info("No ELBs to monitor - skipping health check.")
        return

    elbs_left = elbs_to_monitor

    end_time = datetime.utcnow() + timedelta(seconds=timeout)
    while end_time > datetime.utcnow():
        elbs = get_all_load_balancers(elbs_left)
        for elb in elbs:
            LOG.info("Checking health for ELB: {}".format(elb['LoadBalancerName']))
            all_healthy = True
            for instance in _get_elb_health(elb['LoadBalancerName']):
                if instance['State'] != 'InService':
                    all_healthy = False
                    break

            if all_healthy:
                LOG.info("All instances are healthy, remove {} from list of load balancers {}.".format(
                    elb['LoadBalancerName'], elbs_left
                ))
                elbs_left.remove(elb['LoadBalancerName'])

        LOG.info("Number of load balancers remaining with unhealthy instances: {}".format(len(elbs_left)))
        if not elbs_left:
            LOG.info("All instances in all ELBs are healthy, returning.")
            return
        time.sleep(WAIT_SLEEP_TIME)

    raise TimeoutException("The following ELBs never became healthy: {}".format(elbs_left))
