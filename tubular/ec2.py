"""
Convenience functions built on top of boto that are useful
when we deploy using asgard.
"""
import boto
import logging
from utils import EDC
from boto.exception import EC2ResponseError

LOG = logging.getLogger(__name__)

class ImageNotFoundException(Exception):
    pass

class MissingTagException(Exception):
    pass

def edc_for_ami(ami_id):
    """
    Look up the EDC tags for an AMI.

    Input: An AMI Id.
    Output: An EDC Named Tuple.
    Exceptions:
        - ImageNotFoundException
        - MissingTagException
    """
    LOG.debug("Looking up edc for {}".format(ami_id))
    ec2 = boto.connect_ec2()

    try:
        ami = ec2.get_all_images(ami_id)[0]
    except EC2ResponseError as error:
        raise ImageNotFoundException(error.message)

    tags = ami.tags

    # TODO How do we want to handle these tags not existing?
    # raise an exception maybe? Right now this is not safe.
    try:
        edc = EDC(tags['environment'], tags['deployment'], tags['cluster'])
    except KeyError as ke:
        missing_key = ke.args[0]
        msg = "{} is missing the {} tag.".format(ami_id, missing_key)
        raise MissingTagException(msg)

    LOG.debug("Got EDC for {}: {}".format(ami_id, edc))
    return edc
