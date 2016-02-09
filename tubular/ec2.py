"""
Convenience functions built on top of boto that are useful
when we deploy using asgard.
"""
import boto
import logging
from utils import EDC
from exception import ImageNotFoundException, MissingTagException
from boto.exception import EC2ResponseError

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

    Input: An EDC Tuple.
    Returns: An iterable of cluster names that match an EDC.
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
        tags = dict_from_tag_list(group.tags)
        LOG.debug("Tags for asg {}: {}".format(group.name, tags))
        if all([ tag in tags for tag in ['environment', 'deployment', 'cluster']]):
            group_env = tags['environment']
            group_deployment = tags['deployment']
            group_cluster = tags['cluster']

            group_edc = EDC(group_env, group_deployment, group_cluster)

            if group_edc == edc:
                yield group.name

def dict_from_tag_list(tag_list):
    """
    Take a list of tags and convert it to a dict mapping the
    tag names to the tag values.

    Input:
    [
        Tag(Name=ZZZZZTest-edx-ecommerce),
        Tag(cluster=ecommerce),
        Tag(deployment=edx),
        Tag(environment=zzzzzzzzz),
        Tag(services=ecommerce),
    ]

    Returns: A dictionary mapping tag names to tag values.
    {
        "Name": "ZZZZZTest-edx-ecommerce",
        "cluster": "ecommerce",
        "deployment": "edx",
        "environment": "zzzzzzzzz",
        "services": "ecommerce",
    }
    """
    tag_dict = {}
    for item in tag_list:
        tag_dict[item.key] = item.value

    return tag_dict

