import unittest

import httpretty
from ..asgard import *

from requests.exceptions import ConnectionError
from requests.exceptions import RequestException

sample_cluster_list = """
[
  {
    "cluster": "loadtest-edx-edxapp",
    "autoScalingGroups":
    [
      "loadtest-edx-edxapp-v058",
      "loadtest-edx-edxapp-v059"
    ]
  },
  {
    "cluster": "loadtest-edx-insights",
    "autoScalingGroups":
    [
      "loadtest-edx-insights-v002"
    ]
  },
  {
    "cluster": "loadtest-edx-worker",
    "autoScalingGroups":
    [
      "loadtest-edx-worker-v034"
    ]
  }
]"""

bad_cluster_json1 = """
{
  "foo": {
    "cluster": "loadtest-edx-edxapp",
    "autoScalingGroups":
    [
      "loadtest-edx-edxapp-v058",
      "loadtest-edx-edxapp-v059"
    ]
  }
}"""

bad_cluster_json2 = """
[
  {
    "autoScalingGroups":
    [
      "loadtest-edx-edxapp-v058",
      "loadtest-edx-edxapp-v059"
    ]
  }
]"""


class TestAsgard(unittest.TestCase):

    @httpretty.activate
    def test_clusters_for_asgs(self):
        httpretty.register_uri(
            httpretty.GET,
            CLUSTER_LIST_URL,
            body=sample_cluster_list,
            content_type="application/json")

        relevant_asgs = []
        cluster_names = clusters_for_asgs(relevant_asgs)
        self.assertEqual({}, cluster_names)

        relevant_asgs = ["loadtest-edx-edxapp-v058"]
        expected_clusters = { "loadtest-edx-edxapp" :
                ["loadtest-edx-edxapp-v058", "loadtest-edx-edxapp-v059"]}
        cluster_names = clusters_for_asgs(relevant_asgs)
        self.assertEqual(expected_clusters, cluster_names)

        relevant_asgs = ["loadtest-edx-edxapp-v058", "loadtest-edx-worker-v034"]
        cluster_names = clusters_for_asgs(relevant_asgs)
        self.assertIn("loadtest-edx-edxapp", cluster_names)
        self.assertIn("loadtest-edx-worker", cluster_names)
        self.assertEqual(["loadtest-edx-worker-v034"], cluster_names['loadtest-edx-worker'])
        self.assertEqual(
                ["loadtest-edx-edxapp-v058", "loadtest-edx-edxapp-v059"],
                cluster_names['loadtest-edx-edxapp'])

    def test_bad_endpoint(self):
        relevant_asgs = []
        self.assertRaises(BackendConnectionError, clusters_for_asgs, relevant_asgs)

    @httpretty.activate
    def test_not_json(self):
        httpretty.register_uri(
            httpretty.GET,
            CLUSTER_LIST_URL,
            body="not json data",
            content_type="application/json")

        relevant_asgs = []
        self.assertRaises(BackendDataError, clusters_for_asgs, relevant_asgs)

    @httpretty.activate
    def test_incorrect_json(self):
        # The json is valid but not the structure we expected.
        httpretty.register_uri(
            httpretty.GET,
            CLUSTER_LIST_URL,
            body=bad_cluster_json1,
            content_type="application/json")

        relevant_asgs = []
        self.assertRaises(BackendDataError, clusters_for_asgs, relevant_asgs)

    @httpretty.activate
    def test_incorrect_cluster_json(self):
        httpretty.register_uri(
            httpretty.GET,
            CLUSTER_LIST_URL,
            body=bad_cluster_json2,
            content_type="application/json")

        relevant_asgs = []
        self.assertRaises(BackendDataError, clusters_for_asgs, relevant_asgs)
