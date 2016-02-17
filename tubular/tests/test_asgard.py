import json
import unittest

import httpretty
from ..asgard import *

from ddt import ddt, data, unpack
from requests.exceptions import ConnectionError

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

valid_cluster_info_json = """

[
  {
    "autoScalingGroupName": "loadtest-edx-edxapp-v058",
    "availabilityZones":
    [
      "us-east-1b",
      "us-east-1c"
    ],
    "createdTime": "2016-02-10T12:23:10Z",
    "defaultCooldown": 300,
    "desiredCapacity": 4
  },
  {
    "autoScalingGroupName": "loadtest-edx-edxapp-v059",
    "availabilityZones":
    [
      "us-east-1b",
      "us-east-1c"
    ],
    "createdTime": "2016-02-10T12:23:10Z",
    "defaultCooldown": 300,
    "desiredCapacity": 4
  }
]
"""

failed_sample_task = """
{
  "log":
  [
    "2016-02-11_02:31:18 Started on thread Task:Force Delete Auto Scaling Group 'loadtest-edx-edxapp-v060'.",
    "2016-02-11_02:31:18 Deregistering all instances in 'loadtest-edx-edxapp-v060' from load balancers",
    "2016-02-11_02:31:18 Deregister all instances in Auto Scaling Group 'loadtest-edx-edxapp-v060' from ELBs",
    "2016-02-11_02:31:19 Deleting auto scaling group 'loadtest-edx-edxapp-v060'",
    "2016-02-11_02:31:19 Delete Auto Scaling Group 'loadtest-edx-edxapp-v060'",
    "2016-02-11_02:31:19 Auto scaling group 'loadtest-edx-edxapp-v060' will be deleted after deflation finishes",
    "2016-02-11_02:41:24 Exception: com.netflix.asgard.push.PushException: Timeout waiting 10m for auto scaling group 'loadtest-edx-edxapp-v060' to disappear from AWS."
  ],
  "status": "failed",
  "operation": "",
  "durationString": "10m 6s",
  "updateTime": "2016-02-11 02:41:24 UTC"
}
"""

completed_sample_task = """
{
  "log":
  [
    "2016-02-11_02:31:11 Started on thread Task:Stopping traffic to instances of loadtest-edx-edxapp-v060.",
    "2016-02-11_02:31:11 Disabling new instance launching for auto scaling group 'loadtest-edx-edxapp-v060'",
    "2016-02-11_02:31:12 Disabling instance termination for auto scaling group 'loadtest-edx-edxapp-v060'",
    "2016-02-11_02:31:12 Disabling adding instances to ELB for auto scaling group 'loadtest-edx-edxapp-v060'",
    "2016-02-11_02:31:12 Completed in 0s."
  ],
  "status": "completed",
  "operation": "",
  "durationString": "0s",
  "updateTime": "2016-02-11 02:31:12 UTC"
}
"""

running_sample_task = """
{
  "log":
  [
    "2016-02-11_19:03:34 Started on thread Task:Creating auto scaling group 'loadtest-edx-edxapp-v059', min 4, max 4, traffic prevented.",
    "2016-02-11_19:03:34 Group 'loadtest-edx-edxapp-v059' will start with 0 instances",
    "2016-02-11_19:03:34 Create Auto Scaling Group 'loadtest-edx-edxapp-v059'",
    "2016-02-11_19:03:34 Create Launch Configuration 'loadtest-edx-edxapp-v059-20160211190334' with image 'ami-f2032998'",
    "2016-02-11_19:03:35 Create Autoscaling Group 'loadtest-edx-edxapp-v059'",
    "2016-02-11_19:03:35 Disabling adding instances to ELB for auto scaling group 'loadtest-edx-edxapp-v059'",
    "2016-02-11_19:03:35 Launch Config 'loadtest-edx-edxapp-v059-20160211190334' has been created. Auto Scaling Group 'loadtest-edx-edxapp-v059' has been created. ",
    "2016-02-11_19:03:35 Create 1 LifecycleHook",
    "2016-02-11_19:03:35 Create LifecycleHook with loadtest-edx-GetTrackingLogs",
    "2016-02-11_19:03:36 Resizing group 'loadtest-edx-edxapp-v059' to min 4, max 4",
    "2016-02-11_19:03:36 Setting group 'loadtest-edx-edxapp-v059' to min 4 max 4",
    "2016-02-11_19:03:36 Update Autoscaling Group 'loadtest-edx-edxapp-v059'",
    "2016-02-11_19:03:37 Group 'loadtest-edx-edxapp-v059' has 0 instances. Waiting for 4 to exist."
  ],
  "status": "running",
  "operation": "Group 'loadtest-edx-edxapp-v059' has 0 instances. Waiting for 4 to exist.",
  "durationString": "16s",
  "updateTime": "2016-02-11 19:03:37 UTC"
}
"""

@ddt
class TestAsgard(unittest.TestCase):
    _multiprocess_can_split_ = True

    def test_bad_endpoint(self):
        relevant_asgs = []
        self.assertRaises(ConnectionError, clusters_for_asgs, relevant_asgs)

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

    @data(bad_cluster_json1, bad_cluster_json2)
    @httpretty.activate
    def test_incorrect_json(self, response_json):
        # The json is valid but not the structure we expected.
        httpretty.register_uri(
            httpretty.GET,
            CLUSTER_LIST_URL,
            body=response_json,
            content_type="application/json")

        relevant_asgs = []
        self.assertRaises(BackendDataError, clusters_for_asgs, relevant_asgs)

    @httpretty.activate
    def test_asg_for_cluster(self):
        cluster = "prod-edx-edxapp"
        url = CLUSTER_INFO_URL.format(cluster)
        httpretty.register_uri(
            httpretty.GET,
            url,
            body=valid_cluster_info_json,
            content_type="application/json")

        expected_asgs = [ "loadtest-edx-edxapp-v058", "loadtest-edx-edxapp-v059" ]
        self.assertEqual(expected_asgs, asgs_for_cluster(cluster))

    def test_bad_endpoint(self):
        cluster = "Fake cluster"
        self.assertRaises(ConnectionError, asgs_for_cluster, cluster)

    @httpretty.activate
    def test_asg_for_cluster_incorrect_json(self):
        # The json is valid but not the structure we expected.
        cluster = "prod-edx-edxapp"
        url = CLUSTER_INFO_URL.format(cluster)
        httpretty.register_uri(
            httpretty.GET,
            url,
            body=bad_cluster_json1,
            content_type="application/json")

        self.assertRaises(BackendDataError, asgs_for_cluster, cluster)

    @httpretty.activate
    def test_task_completion(self):
        task_url = "http://some.host/task/1234.json"
        httpretty.register_uri(
            httpretty.GET,
            task_url,
            body=completed_sample_task,
            content_type="application/json")

        actual_output = wait_for_task_completion(task_url, 1)
        expected_output = json.loads(completed_sample_task)
        self.assertEqual(expected_output, actual_output)

    @httpretty.activate
    def test_failed_task_completion(self):
        task_url = "http://some.host/task/1234.json"
        httpretty.register_uri(
            httpretty.GET,
            task_url,
            body=failed_sample_task,
            content_type="application/json")

        actual_output = wait_for_task_completion(task_url, 1)
        expected_output = json.loads(failed_sample_task)
        self.assertEqual(expected_output, actual_output)

    @httpretty.activate
    def test_failed_task_completion(self):
        task_url = "http://some.host/task/1234.json"
        httpretty.register_uri(
            httpretty.GET,
            task_url,
            responses=[
                httpretty.Response(body=running_sample_task),
                httpretty.Response(failed_sample_task),
                ],
            content_type="application/json")

        actual_output = wait_for_task_completion(task_url, 2)
        expected_output = json.loads(failed_sample_task)
        self.assertEqual(expected_output, actual_output)

    @httpretty.activate
    def test_task_timeout(self):
        task_url = "http://some.host/task/1234.json"
        httpretty.register_uri(
            httpretty.GET,
            task_url,
            body=running_sample_task,
            content_type="application/json")

        self.assertRaises(TimeoutException, wait_for_task_completion, task_url, 1)

    @httpretty.activate
    def test_new_asg(self):
        task_url = "http://some.host/task/1234.json"
        cluster = "loadtest-edx-edxapp"
        ami_id = "ami-abc1234"

        def post_callback(request, uri, headers):
            self.assertEqual('POST', request.method)
            expected_request_body = { "name" : [cluster], "imageId": [ami_id] }
            expected_querystring = { "asgardApiToken": ['dummy-token'] }

            self.assertEqual(expected_request_body, request.parsed_body)
            self.assertEqual(expected_querystring, request.querystring)
            response_headers = { "Location": task_url,
                    "server": ASGARD_API_ENDPOINT}
            response_body = ""
            return (302, response_headers, response_body)

        httpretty.register_uri(
                httpretty.POST,
                NEW_ASG_URL,
                body=post_callback,
                Location=task_url)

        httpretty.register_uri(
            httpretty.GET,
            task_url,
            body=completed_sample_task,
            content_type="application/json")

        url = CLUSTER_INFO_URL.format(cluster)
        httpretty.register_uri(
            httpretty.GET,
            url,
            body=valid_cluster_info_json,
            content_type="application/json")

        expected_asg = "loadtest-edx-edxapp-v059"
        self.assertEqual(expected_asg, new_asg(cluster,ami_id))

    @httpretty.activate
    def test_new_asg_failure(self):
        task_url = "http://some.host/task/1234.json"
        cluster = "loadtest-edx-edxapp"
        ami_id = "ami-abc1234"

        def post_callback(request, uri, headers):
            self.assertEqual('POST', request.method)
            expected_request_body = { "name" : [cluster], "imageId": [ami_id] }
            expected_querystring = { "asgardApiToken": ['dummy-token'] }

            self.assertEqual(expected_request_body, request.parsed_body)
            self.assertEqual(expected_querystring, request.querystring)
            response_headers = { "Location": task_url.strip(".json"),
                    "server": ASGARD_API_ENDPOINT}
            response_body = ""
            return (302, response_headers, response_body)

        httpretty.register_uri(
                httpretty.POST,
                NEW_ASG_URL,
                body=post_callback,
                Location=task_url)

        httpretty.register_uri(
            httpretty.GET,
            task_url,
            body=failed_sample_task,
            content_type="application/json")

        url = CLUSTER_INFO_URL.format(cluster)
        httpretty.register_uri(
            httpretty.GET,
            url,
            body=valid_cluster_info_json,
            content_type="application/json")

        self.assertRaises(BackendError, new_asg,cluster,ami_id)

    @httpretty.activate
    @data((ASG_ACTIVATE_URL, enable_asg), (ASG_DEACTIVATE_URL, disable_asg))
    @unpack
    def test_enable_disable_asg_success(self, endpoint_url, test_function):
        task_url = "http://some.host/task/1234.json"
        asg = "loadtest-edx-edxapp-v059"

        def post_callback(request, uri, headers):
            self.assertEqual('POST', request.method)
            expected_request_body = { "name" : [asg] }
            expected_querystring = { "asgardApiToken": ['dummy-token'] }

            self.assertEqual(expected_request_body, request.parsed_body)
            self.assertEqual(expected_querystring, request.querystring)
            response_headers = { "Location": task_url.strip(".json"),
                    "server": ASGARD_API_ENDPOINT}
            response_body = ""
            return (302, response_headers, response_body)

        httpretty.register_uri(
                httpretty.POST,
                endpoint_url,
                body=post_callback)

        httpretty.register_uri(
            httpretty.GET,
            task_url,
            body=completed_sample_task,
            content_type="application/json")

        self.assertEquals(None, test_function(asg))

    @httpretty.activate
    @data((ASG_ACTIVATE_URL, enable_asg), (ASG_DEACTIVATE_URL, disable_asg))
    @unpack
    def test_enable_disable_asg_failure(self, endpoint_url, test_function):
        task_url = "http://some.host/task/1234.json"
        asg = "loadtest-edx-edxapp-v059"

        def post_callback(request, uri, headers):
            self.assertEqual('POST', request.method)
            expected_request_body = { "name" : [asg] }
            expected_querystring = { "asgardApiToken": ['dummy-token'] }

            self.assertEqual(expected_request_body, request.parsed_body)
            self.assertEqual(expected_querystring, request.querystring)
            response_headers = { "Location": task_url.strip(".json"),
                    "server": ASGARD_API_ENDPOINT}
            response_body = ""
            return (302, response_headers, response_body)

        httpretty.register_uri(
                httpretty.POST,
                endpoint_url,
                body=post_callback)

        httpretty.register_uri(
            httpretty.GET,
            task_url,
            body=failed_sample_task,
            content_type="application/json")

        self.assertRaises(BackendError, test_function, asg)
