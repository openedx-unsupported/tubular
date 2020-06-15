"""
Initialization code for the utils module.
"""

import os
from collections import namedtuple

from six.moves import range

# Time in seconds to wait between polls of Asgard or AWS.
WAIT_SLEEP_TIME = int(os.environ.get("WAIT_SLEEP_TIME", 5))

# Time in seconds to wait between when new ASGs are enabled -and- when health checks
# are performed on those new ASGs in order to begin disabling old ASGs.
DISABLE_OLD_ASG_WAIT_TIME = int(os.environ.get("DISABLE_OLD_ASG_WAIT_TIME", 0))

EDP = namedtuple('EDP', ['environment', 'deployment', 'play'])


def exactly_one_set(param_list):
    """
    Guarantees that only one of the cmd-line params list have a value set.
    """
    return sum(int(bool(param)) for param in param_list) == 1


def envvar_get_int(var_name, default):
    """
    Grab an environment variable and return it as an integer.
    If the environment variable does not exist, return the default.
    """
    return int(os.environ.get(var_name, default))


def batch(batchable, batch_size=1):
    """
    Utility to facilitate batched iteration over a list.

    Arguments:
        batchable (list): The list to break into batches.

    Yields:
        list
    """
    batchable_list = list(batchable)
    length = len(batchable_list)
    for index in range(0, length, batch_size):
        yield batchable_list[index:index + batch_size]
