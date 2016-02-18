import os
import logging
import requests
from requests.exceptions import ConnectionError
from collections import Iterable
from .exception import *

ASGARD_API_ENDPOINT = os.environ.get("ASGARD_API_ENDPOINTS", "http://dummy.url:8091")
ASGARD_API_TOKEN = os.environ.get("ASGARD_API_TOKEN")

CLUSTER_LIST_URL= "{}/cluster/list.json".format(ASGARD_API_ENDPOINT)

LOG = logging.getLogger(__name__)

def clusters_for_asgs(asgs):
    """
    An autoscaling group can belong to multiple clusters potentially.

    This function finds all asgard clusters for a list of ASGs.
    eg. get all clusters that have the 'edxapp' cluster tag..

    Input:
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
    response = requests.get(CLUSTER_LIST_URL, params=ASGARD_API_TOKEN)
    cluster_json = response.json()

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
