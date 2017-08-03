"""
Convenience functions built on top of boto that are useful
when we deploy using asgard.
"""
from __future__ import absolute_import
from __future__ import unicode_literals

import os
import logging
import re
import time
from datetime import datetime, timedelta
import backoff
import boto
from boto.exception import EC2ResponseError, BotoServerError
from boto.ec2.autoscale.tag import Tag
import boto3
import botocore.exceptions  # use botocore.exceptions.ClientError instead of BotoServerError for boto3 exceptions
from tubular.utils import EDP, WAIT_SLEEP_TIME
from tubular.exception import (
    ImageNotFoundException,
    MultipleImagesFoundException,
    MissingTagException,
    TimeoutException,
)

LOG = logging.getLogger(__name__)

ISO_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
ASG_DELETE_TAG_KEY = 'delete_on_ts'
MAX_ATTEMPTS = os.environ.get('RETRY_MAX_ATTEMPTS', 5)
RETRY_FACTOR = os.environ.get('RETRY_FACTOR', 1.5)


# TODO: determine if we need to handle the situation where max retry attempts was reached.
def giveup_if_not_throttling(ex):
    """
    Checks if a BotoServerError/ClientError exception indicates non-throttling related error.

    If this check returns True, it suggests that retry handlers should give up.

    Args:
        ex (boto.exception.BotoServerError or botocore.exceptions.ClientError):

    Returns:
        boolean: True if the exception indicates non-throttling related error.

    Raises:
        ValueError: the exception parameter is not a boto error response.
    """
    if isinstance(ex, BotoServerError):
        status_code = ex.status
        message = ex.body
    elif isinstance(ex, botocore.exceptions.ClientError):
        status_code = ex.response['Error'].get('Code', 'Unknown')
        message = ex.response['Error'].get('Message', 'Unknown')
    else:
        raise ValueError('Expecting the parameter to be either boto.exception.BotoServerError (boto2) or ' +
                         'botocore.exceptions.ClientError (boto3), instead got {}'.format(type(ex)))

    return not (str(status_code) == '400' and message and '<Code>Throttling</Code>' in message)


@backoff.on_exception(backoff.expo,
                      BotoServerError,
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
    autoscale_conn = boto.connect_autoscale()
    fetched_asgs = autoscale_conn.get_all_groups(names=names)
    total_asgs = []
    while True:
        total_asgs.extend([asg for asg in fetched_asgs])
        if fetched_asgs.next_token:
            fetched_asgs = autoscale_conn.get_all_groups(names=names, next_token=fetched_asgs.next_token)
        else:
            break
    return total_asgs


@backoff.on_exception(backoff.expo,
                      BotoServerError,
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
    elb_conn = boto.connect_elb()
    fetched_elbs = elb_conn.get_all_load_balancers(names)
    total_elbs = []
    while True:
        total_elbs.extend([elb for elb in fetched_elbs])
        if fetched_elbs.next_token:
            fetched_elbs = elb_conn.get_all_load_balancers(names, fetched_elbs.next_token)
        else:
            break
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
                      BotoServerError,
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
    ec2_conn = boto.connect_ec2()
    all_elbs = get_all_load_balancers()
    LOG.info("Found {} load balancers.".format(len(all_elbs)))

    edp_filter = {
        "tag:environment": env,
        "tag:deployment": dep,
        "tag:play": play,
    }
    reservations = ec2_conn.get_all_reservations(filters=edp_filter)
    LOG.info("{} reservations found for EDP {}-{}-{}".format(len(reservations), env, dep, play))
    amis = set()
    for reservation in reservations:
        for instance in reservation.instances:
            elbs = _instance_elbs(instance.id, all_elbs)
            if instance.state == 'running' and len(elbs) > 0:
                amis.add(instance.image_id)
                LOG.info("AMI found for {}-{}-{}: {}".format(env, dep, play, instance.image_id))
            else:
                LOG.info("Instance {} state: {} - elbs in: {}".format(instance.id, instance.state, len(elbs)))

    if len(amis) > 1:
        msg = "Multiple AMIs found for {}-{}-{}, should have only one.".format(env, dep, play)
        raise MultipleImagesFoundException(msg)

    if len(amis) == 0:
        msg = "No AMIs found for {}-{}-{}.".format(env, dep, play)
        raise ImageNotFoundException(msg)

    return amis.pop()


@backoff.on_exception(backoff.expo,
                      BotoServerError,
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
    ec2 = boto.connect_ec2()

    try:
        ami = ec2.get_all_images(ami_id)[0]
    except IndexError:
        raise ImageNotFoundException("ami: {} not found".format(ami_id))
    except EC2ResponseError as error:
        raise ImageNotFoundException(str(error))

    return ami.tags


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
        edp = EDP(tags['environment'], tags['deployment'], tags['play'])
    except KeyError as key_err:
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
    edp_matched = (
        edp.environment == environment and
        edp.deployment == deployment and
        edp.play == play
    )
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


def asgs_for_edp(edp, filter_asgs_pending_delete=True, regex_filter=None):
    """
    All AutoScalingGroups that have the tags of this play.

    A play is made up of many auto_scaling groups.

    Arguments:
        edp (EDP Named Tuple): The edp tags for the ASGs you want.
        filter_asgs_pending_delete (bool): Do not include ASGs tagged for deletion.
        regex_filter (str): Only include ASGs matching this regex.
    Returns:
        list: list of ASG names that match the EDP and given filters.
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
        filter_this_group = False
        tags = {tag.key: tag.value for tag in group.tags}
        LOG.debug("Tags for asg {}: {}".format(group.name, tags))
        if filter_asgs_pending_delete and ASG_DELETE_TAG_KEY in tags.keys():
            LOG.info('filtering out ASG "{0}" because it is tagged for deletion on "{1}"'
                     .format(group.name, tags[ASG_DELETE_TAG_KEY]))
            filter_this_group = True
        if regex_filter is not None and not re.match(regex_filter, group.name):
            LOG.info('filtering out ASG "{0}" because it does not match the regex filter "{1}"'
                     .format(group.name, regex_filter))
            filter_this_group = True
        if filter_this_group:
            # for one or more reasons this group has been filtered out, so do
            # not consider it for addition to the output.
            continue

        edp_keys = ['environment', 'deployment', 'play']
        if all([tag in tags for tag in edp_keys]):
            group_env = tags['environment']
            group_deployment = tags['deployment']
            group_play = tags['play']

            group_edp = EDP(group_env, group_deployment, group_play)

            if group_edp == edp:
                matching_groups.append(group.name)

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
    return Tag(key=ASG_DELETE_TAG_KEY,
               value=tag_value,
               propagate_at_launch=False,
               resource_id=asg_name)


@backoff.on_exception(backoff.expo,
                      BotoServerError,
                      max_tries=MAX_ATTEMPTS,
                      giveup=giveup_if_not_throttling,
                      factor=RETRY_FACTOR)
def tag_asg_for_deletion(asg_name, seconds_until_delete_delta=1800):
    """
    Tag an asg with a tag named ASG_DELETE_TAG_KEY with a value of the MS since epoch UTC + ms_until_delete_delta
    that an ASG may be deleted.

    Arguments:
        asg_name (str): the name of the autoscale group to tag

    Returns:
        None
    """
    tag = create_tag_for_asg_deletion(asg_name, seconds_until_delete_delta)
    autoscale = boto.connect_autoscale()
    if len(get_all_autoscale_groups([asg_name])) < 1:
        LOG.info("ASG {} no longer exists, will not tag".format(asg_name))
    else:
        autoscale.create_or_update_tags([tag])


@backoff.on_exception(backoff.expo,
                      BotoServerError,
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
            for tag in asg.tags:
                if tag.key == ASG_DELETE_TAG_KEY:
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
        LOG.debug("Checking for {0} on asg: {1}".format(ASG_DELETE_TAG_KEY, asg.name))
        for tag in asg.tags:
            try:
                if tag.key == ASG_DELETE_TAG_KEY:
                    LOG.debug("Found {0} tag, deletion time: {1}".format(ASG_DELETE_TAG_KEY, tag.value))
                    if datetime.strptime(tag.value, ISO_DATE_FORMAT) - current_datetime < timedelta(0, 0, 0):
                        LOG.debug("Adding ASG: {0} to the list of ASGs to delete.".format(asg.name))
                        asgs_pending_delete.append(asg)
                        break
            except ValueError:
                LOG.warning(
                    "ASG {0} has an improperly formatted datetime string for the key {1}. Value: {2} . "
                    "Format must match {3}".format(
                        asg.name, tag.key, tag.value, ISO_DATE_FORMAT
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
    conn = boto.ec2.connect_to_region(region)
    instances_to_terminate = []

    reservations = conn.get_all_instances(filters=tags)
    for reservation in reservations:
        for instance in reservation.instances:
            total_run_time = datetime.utcnow() - datetime.strptime(instance.launch_time[:-1], ISO_DATE_FORMAT)
            if total_run_time > timedelta(hours=max_run_hours) and skip_if_tag not in instance.tags:
                instances_to_terminate.append(instance.id)
    if len(instances_to_terminate) > 0:
        conn.terminate_instances(instance_ids=instances_to_terminate)
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
    if len(all_asgs) == 0:
        LOG.info("No ASGs to monitor - skipping health check.")
        return

    asgs_left_to_check = list(all_asgs)
    LOG.info("Waiting for ASGs to be healthy: {}".format(asgs_left_to_check))

    end_time = datetime.utcnow() + timedelta(seconds=timeout)
    while end_time > datetime.utcnow():
        asgs = get_all_autoscale_groups(asgs_left_to_check)
        for asg in asgs:
            all_healthy = True
            for instance in asg.instances:
                if instance.health_status.lower() != 'healthy' or instance.lifecycle_state.lower() != 'inservice':
                    # Instance is not ready.
                    all_healthy = False
                    break

            if all_healthy:
                # Then all are healthy we can stop checking this.
                LOG.debug("All instances healthy in ASG: {}".format(asg.name))
                LOG.debug(asgs_left_to_check)
                asgs_left_to_check.remove(asg.name)

        if len(asgs_left_to_check) == 0:
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

    @backoff.on_exception(backoff.expo,
                          BotoServerError,
                          max_tries=MAX_ATTEMPTS,
                          giveup=giveup_if_not_throttling,
                          factor=RETRY_FACTOR)
    def _get_elb_health(selected_elb):
        """
        Get the health of an ELB

        Args:
            selected_elb (boto.ec2.elb.loadbalancer.LoadBalancer):

        Returns:
            list of InstanceState <boto.ec2.elb.instancestate.InstanceState>

        """
        return selected_elb.get_instance_health()

    if len(elbs_to_monitor) == 0:
        LOG.info("No ELBs to monitor - skipping health check.")
        return

    elbs_left = set(elbs_to_monitor)
    end_time = datetime.utcnow() + timedelta(seconds=timeout)
    while end_time > datetime.utcnow():
        elbs = get_all_load_balancers(elbs_left)
        for elb in elbs:
            LOG.info("Checking health for ELB: {}".format(elb.name))
            all_healthy = True
            for instance in _get_elb_health(elb):
                if instance.state != 'InService':
                    all_healthy = False
                    break

            if all_healthy:
                LOG.info("All instances are healthy, remove {} from list of load balancers {}.".format(
                    elb.name, elbs_left
                ))
                elbs_left.remove(elb.name)

        LOG.info("Number of load balancers remaining with unhealthy instances: {}".format(len(elbs_left)))
        if len(elbs_left) == 0:
            LOG.info("All instances in all ELBs are healthy, returning.")
            return
        time.sleep(WAIT_SLEEP_TIME)

    raise TimeoutException("The following ELBs never became healthy: {}".format(elbs_left))


@backoff.on_exception(backoff.expo,
                      botocore.exceptions.ClientError,
                      max_tries=MAX_ATTEMPTS,
                      giveup=giveup_if_not_throttling,
                      factor=RETRY_FACTOR)
def ensure_cloudwatch_alarm(region, **kwargs):
    """
    Ensure there is a cloudwatch alarm as defined.

    Arguments:
        region (str): name of AWS region where to create alarm
        **kwargs: Passthrough options to boto3 put_metric_alarm():
            http://boto3.readthedocs.io/en/latest/reference/services/cloudwatch.html#CloudWatch.Client.put_metric_alarm

    Returns:
        Nothing, since the underlying call put_metric_alarm() returns nothing.
    """
    client = boto3.client('cloudwatch', region_name=region)
    client.put_metric_alarm(**kwargs)


@backoff.on_exception(backoff.expo,
                      botocore.exceptions.ClientError,
                      max_tries=MAX_ATTEMPTS,
                      giveup=giveup_if_not_throttling,
                      factor=RETRY_FACTOR)
def ensure_asg_scaling_policy(region, **kwargs):
    """
    Ensure there is an ASG scaling policy as defined.

    Arguments:
        region (str): name of AWS region where to create policy
        **kwargs: Passthrough options to boto3 put_scaling_policy():
            http://boto3.readthedocs.io/en/latest/reference/services/autoscaling.html#AutoScaling.Client.put_scaling_policy

    Returns:
        dict: Response object from the put_scaling_policy() call.  At minimum,
            this dict contains a 'PolicyARN' key whose value represents the ARN
            of the newly created or modified scaling policy.
    """
    client = boto3.client('autoscaling', region_name=region)
    response = client.put_scaling_policy(**kwargs)
    return response


@backoff.on_exception(backoff.expo,
                      botocore.exceptions.ClientError,
                      max_tries=MAX_ATTEMPTS,
                      giveup=giveup_if_not_throttling,
                      factor=RETRY_FACTOR)
def describe_asg_scaling_policies(region, **kwargs):
    """
    Simple passthrough function to describe_policies() adding retry behavior.
    """
    client = boto3.client('autoscaling', region_name=region)
    response = client.describe_policies(**kwargs)
    return response


@backoff.on_exception(backoff.expo,
                      botocore.exceptions.ClientError,
                      max_tries=MAX_ATTEMPTS,
                      giveup=giveup_if_not_throttling,
                      factor=RETRY_FACTOR)
def describe_cloudwatch_alarms(region, **kwargs):
    """
    Simple passthrough function to describe_alarms() adding retry behavior.
    """
    client = boto3.client('cloudwatch', region_name=region)
    response = client.describe_alarms(**kwargs)
    return response
