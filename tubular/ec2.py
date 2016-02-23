"""
Convenience functions built on top of boto that are useful
when we deploy using asgard.
"""
import boto
import logging
import time
from utils import EDC
from exception import ImageNotFoundException
from exception import MissingTagException
from exception import TimeoutException
from boto.exception import EC2ResponseError
from datetime import datetime, timedelta

LOG = logging.getLogger(__name__)


def edc_for_ami(ami_id):
    """
    Look up the EDC tags for an AMI.

    Arguments:
        ami_id (str): An AMI Id.
    Returns:
        EDC Named Tuple: The EDC tags for this AMI.
    Raises:
        ImageNotFoundException: No image found with this ami ID.
        MissingTagException: AMI is missing one or more of the expected tags.
    """
    LOG.debug("Looking up edc for {}".format(ami_id))
    ec2 = boto.connect_ec2()

    try:
        ami = ec2.get_all_images(ami_id)[0]
    except EC2ResponseError as error:
        raise ImageNotFoundException(error.message)

    tags = ami.tags

    try:
        edc = EDC(tags['environment'], tags['deployment'], tags['cluster'])
    except KeyError as ke:
        missing_key = ke.args[0]
        msg = "{} is missing the {} tag.".format(ami_id, missing_key)
        raise MissingTagException(msg)

    LOG.debug("Got EDC for {}: {}".format(ami_id, edc))
    return edc


def asgs_for_edc(edc):
    """
    All AutoScalingGroups that have the tags of this cluster.

    A cluster is made up of many auto_scaling groups.

    Arguments:
        EDC Named Tuple: The edc tags for the ASGs you want.
    Returns:
        iterable: An iterable of cluster names that match the EDC.
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
        tags = { tag.key: tag.value for tag in group.tags }
        LOG.debug("Tags for asg {}: {}".format(group.name, tags))
        edc_keys = ['environment', 'deployment', 'cluster']
        if all([tag in tags for tag in edc_keys]):
            group_env = tags['environment']
            group_deployment = tags['deployment']
            group_cluster = tags['cluster']

            group_edc = EDC(group_env, group_deployment, group_cluster)

            if group_edc == edc:
                yield group.name

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
    elbs_left = list(elbs_to_monitor)
    end_time = datetime.utcnow() + timedelta(seconds=timeout)
    while end_time > datetime.utcnow():
        elbs = boto_elb.get_all_load_balancers(elbs_to_monitor)
        for elb in elbs:
            all_healthy = True
            for instance in elb.get_instance_health():
                if instance.state != 'InService':
                    all_healthy = False
                    break

            if all_healthy:
                elbs_left.remove(elb.name)

        if len(elbs_left) == 0:
            return
        time.sleep(1)

    raise TimeoutException("The following ELBs never became healthy: {}".format(elbs_left))
