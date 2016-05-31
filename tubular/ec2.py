"""
Convenience functions built on top of boto that are useful
when we deploy using asgard.
"""
import boto
import logging
import time
from tubular.utils import EDP
from tubular.exception import (
    ImageNotFoundException,
    MissingTagException,
    TimeoutException,
    ASGDoesNotExistException
)
from boto.exception import EC2ResponseError
from boto.ec2.autoscale.tag import Tag
from datetime import datetime, timedelta

LOG = logging.getLogger(__name__)

ISO_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
ASG_DELETE_TAG_KEY = 'delete_on_ts'


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
    LOG.debug("Looking up edp for {}".format(ami_id))
    ec2 = boto.connect_ec2()

    try:
        ami = ec2.get_all_images(ami_id)[0]
    except EC2ResponseError as error:
        raise ImageNotFoundException(error.message)

    tags = ami.tags

    try:
        edp = EDP(tags['environment'], tags['deployment'], tags['play'])
    except KeyError as ke:
        missing_key = ke.args[0]
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
        LOG.info("AMI {0} EDP did not match specified: {1} != ({2}, {3}, {4})".format(ami_id, edp, environment, deployment, play))
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
        iterable: An iterable of ASG names that match the EDP.
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
    autoscale = boto.connect_autoscale()
    all_groups = autoscale.get_all_groups()
    LOG.debug("All groups: {}".format(all_groups))
    for group in all_groups:
        tags = {tag.key: tag.value for tag in group.tags}
        LOG.debug("Tags for asg {}: {}".format(group.name, tags))
        if filter_asgs_pending_delete and ASG_DELETE_TAG_KEY in tags.keys():
            LOG.info("filtering ASG: {0} because it is tagged for deletion on: {1}"
                     .format(group.name, tags[ASG_DELETE_TAG_KEY]))
            continue

        edp_keys = ['environment', 'deployment', 'play']
        if all([tag in tags for tag in edp_keys]):
            group_env = tags['environment']
            group_deployment = tags['deployment']
            group_play = tags['play']

            group_edp = EDP(group_env, group_deployment, group_play)

            if group_edp == edp:
                yield group.name


def create_tag_for_asg_deletion(asg_name, seconds_until_delete_delta=3600):
    return Tag(key=ASG_DELETE_TAG_KEY,
               value=(datetime.utcnow() + timedelta(seconds=seconds_until_delete_delta)).isoformat(),
               propagate_at_launch=False,
               resource_id=asg_name)


def tag_asg_for_deletion(asg_name, seconds_until_delete_delta=3600):
    """
    Tag an asg with a tag named ASG_DELETE_TAG_KEY with a value of the MS since epoch UTC + ms_until_delete_delta
    that an ASG may be deleted.

    Arguments:
        asg_name (str): the name of the autoscale group to tag

    Returns:
        None

    Raises:
        ASGDoesNotExistException: if the Autoscale group does not exist
    """
    tag = create_tag_for_asg_deletion(asg_name, seconds_until_delete_delta)
    autoscale = boto.connect_autoscale()
    if len(autoscale.get_all_groups([asg_name])) < 1:
        raise ASGDoesNotExistException("Could not apply tags to Autoscale group: {0} does not exist.".format(asg_name))
    autoscale.create_or_update_tags([tag])


def get_asgs_pending_delete():
    """
    Get a list of all the autoscale groups marked with the ASG_DELETE_TAG_KEY. Return only those groups who's ASG_DELETE_TAG_KEY
    as past the current time.

    It's intended for this method to be robust and to return as many ASGs that are pending delete as possible even if
    an error occurs during the process.

    Returns:
        List(<boto.ec2.autoscale.group.AutoScalingGroup>)
    """
    current_datetime = datetime.utcnow()
    autoscale = boto.connect_autoscale()
    asgs_pending_delete = []
    asgs = autoscale.get_all_groups()

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
            except ValueError as e:
                LOG.warn("ASG {0} has an improperly formatted datetime string for the key {1}. Value: {2} . "
                         "Format must match {3}"
                         .format(asg.name, tag.key, tag.value, ISO_DATE_FORMAT))
                continue
            except Exception as e:
                LOG.warn("Error occured while building a list of ASGs to delete, continuing: {0}".format(e.message))
                continue

    LOG.info("Number of ASGs pending delete: {0}".format(len(asgs_pending_delete)))
    return asgs_pending_delete


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

    autoscale = boto.connect_autoscale()
    time_left = timeout
    asgs_left_to_check = list(all_asgs)
    LOG.info("Waiting for ASGs to be healthy: {}".format(asgs_left_to_check))

    end_time = datetime.utcnow() + timedelta(seconds=timeout)
    while end_time > datetime.utcnow():
        asgs = autoscale.get_all_groups(asgs_left_to_check)
        for asg in asgs:
            all_healthy = True
            for instance in asg.instances:
                if instance.health_status.lower() != 'healthy' or instance.lifecycle_state.lower() != 'inservice':
                    # Instance is  not ready.
                    all_healthy = False
                    break

            if all_healthy:
                # Then all are healthy we can stop checking this.
                LOG.debug("All instances healthy in ASG: {}".format(asg.name))
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
    boto_elb = boto.connect_elb()
    elbs_left = set(elbs_to_monitor)
    end_time = datetime.utcnow() + timedelta(seconds=timeout)
    while end_time > datetime.utcnow():
        elbs = boto_elb.get_all_load_balancers(elbs_left)
        for elb in elbs:
            LOG.info("Checking health for ELB: {}".format(elb.name))
            all_healthy = True
            for instance in elb.get_instance_health():
                if instance.state != 'InService':
                    all_healthy = False
                    break

            if all_healthy:
                LOG.info("All instances are healthy, remove {} from list of load balancers {}.".format(elb.name, elbs_left))
                elbs_left.remove(elb.name)

        LOG.info("Number of load balancers remaining with unhealthy instances: {}".format(len(elbs_left)))
        if len(elbs_left) == 0:
            LOG.info("All instances in all ELBs are healthy, returning.")
            return
        time.sleep(1)

    raise TimeoutException("The following ELBs never became healthy: {}".format(elbs_left))
