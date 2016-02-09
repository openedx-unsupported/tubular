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
