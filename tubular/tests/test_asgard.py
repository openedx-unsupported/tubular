import json
import unittest
import itertools

import boto
import mock
import httpretty
from ..asgard import *
from ..exception import *

from ddt import ddt, data, unpack
from moto import mock_ec2, mock_autoscaling, mock_elb
from moto.ec2.utils import random_ami_id
from requests.exceptions import ConnectionError

from .test_utils import create_asg_with_tags, create_elb

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
asgs_for_edxapp_before = """
[
  {
    "autoScalingGroupName": "loadtest-edx-edxapp-v058"
  },
  {
    "autoScalingGroupName": "loadtest-edx-edxapp-v059"
  }
]
"""

asgs_for_edxapp_after = """
[
  {
    "autoScalingGroupName": "loadtest-edx-edxapp-v058"
  },
  {
    "autoScalingGroupName": "loadtest-edx-edxapp-v059"
  },
  {
    "autoScalingGroupName": "loadtest-edx-edxapp-v099"
  }
]
"""

asgs_for_worker_before = """
[
  {
    "autoScalingGroupName": "loadtest-edx-worker-v034"
  }
]
"""
asgs_for_worker_after = """
[
  {
    "autoScalingGroupName": "loadtest-edx-worker-v034"
  },
  {
    "autoScalingGroupName": "loadtest-edx-worker-v099"
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

sample_asg_info = """
{
  "group": {
    "loadBalancerNames":
    [
      "app_elb"
    ]
  }
}
"""

sample_worker_asg_info = """
{
  "group": {
    "loadBalancerNames": []
  }
}
"""

@ddt
class TestAsgard(unittest.TestCase):
    _multiprocess_can_split_ = True

    def test_bad_clusters_endpoint(self):
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

    def test_bad_asgs_endpoint(self):
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
    def test_elbs_for_asg(self):
        asg_info_url = ASG_INFO_URL.format("test_asg")
        httpretty.register_uri(
            httpretty.GET,
            asg_info_url,
            body=sample_asg_info,
            content_type="application/json")

        self.assertEqual( elbs_for_asg("test_asg"), [ "app_elb" ])

    @httpretty.activate
    def test_elbs_for_asg_bad_data(self):
        asg_info_url = ASG_INFO_URL.format("test_asg")
        httpretty.register_uri(
            httpretty.GET,
            asg_info_url,
            body=bad_cluster_json1,
            content_type="application/json")

        self.assertRaises(BackendDataError, elbs_for_asg, "test_asg")

    def test_bad_asg_info_endpoint(self):
        asg = "fake_asg"
        self.assertRaises(ConnectionError, elbs_for_asg, "fake_asg")

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
    @mock.patch('boto.connect_autoscale')
    def test_disable_asg_pending_deletion(self, mock_connect_autoscale):
        """
        Tests an ASG disable that is cancelled due to the ASG pending deletion.
        """
        # Set up the mocking of the boto ASG calls.
        mock_inst0 = mock.Mock()
        mock_inst0.lifecycle_state = "InService"
        mock_inst1 = mock.Mock()
        mock_inst1.lifecycle_state = "Terminating:Wait"
        mock_group0 = mock.Mock()
        mock_group0.instances = [ mock_inst0, mock_inst1 ]
        mock_get_all_groups = mock.Mock()
        mock_get_all_groups.get_all_groups.return_value = [ mock_group0, mock.Mock() ]
        mock_connect_autoscale.return_value = mock_get_all_groups

        def post_callback(request, uri, headers):
            # If this POST callback gets called, test has failed.
            raise Exception("POST called to disable ASG when it should have been skipped.")

        httpretty.register_uri(
            httpretty.POST,
            ASG_DEACTIVATE_URL,
            body=post_callback
        )

        self.assertEquals(None, disable_asg("loadtest-edx-edxapp-v059"))

    @httpretty.activate
    @mock_autoscaling
    @mock_ec2
    @data(*itertools.product(
        ((ASG_ACTIVATE_URL, enable_asg), (ASG_DEACTIVATE_URL, disable_asg)),
        (True, False)
    ))
    @unpack
    def test_enable_disable_asg(self, url_and_function, success):
        """
        Tests enabling and disabling ASGs, with both success and failure.
        """
        endpoint_url, test_function = url_and_function
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
            body=post_callback
        )

        httpretty.register_uri(
            httpretty.GET,
            task_url,
            body=completed_sample_task if success else failed_sample_task,
            content_type="application/json"
        )

        if success:
            self.assertEquals(None, test_function(asg))
        else:
            self.assertRaises(BackendError, test_function, asg)

    def _setup_for_deploy(self,
            new_asg_task_status=completed_sample_task,
            enable_asg_task_status=completed_sample_task,
            disable_asg_task_status=completed_sample_task,
        ):
        # Make the AMI
        ec2 = boto.connect_ec2()
        reservation = ec2.run_instances(random_ami_id())
        instance_id = reservation.instances[0].id
        ami_id = ec2.create_image(instance_id, "Existing AMI")
        ami = ec2.get_all_images(ami_id)[0]
        ami.add_tag("environment", "foo")
        ami.add_tag("deployment", "bar")
        ami.add_tag("play", "baz")

        # Make the current ASGs
        asg_tags = { "environment": "foo",
            "deployment": "bar",
            "play": "baz",
        }

        elb_name = "app_elb"
        create_elb(elb_name)

        create_asg_with_tags("loadtest-edx-edxapp-v058", asg_tags, ami_id, [elb_name])
        create_asg_with_tags("loadtest-edx-edxapp-v059", asg_tags, ami_id, [elb_name])
        create_asg_with_tags("loadtest-edx-worker-v034", asg_tags, ami_id, [])

        httpretty.register_uri(
            httpretty.GET,
            CLUSTER_LIST_URL,
            body=sample_cluster_list,
            content_type="application/json")

        edxapp_cluster_info_url = CLUSTER_INFO_URL.format("loadtest-edx-edxapp")
        httpretty.register_uri(
            httpretty.GET,
            edxapp_cluster_info_url,
            responses=[
#                httpretty.Response(body=asgs_for_edxapp_before),
                httpretty.Response(body=asgs_for_edxapp_after),
                ],
        )

        worker_cluster_info_url = CLUSTER_INFO_URL.format("loadtest-edx-worker")
        httpretty.register_uri(
            httpretty.GET,
            worker_cluster_info_url,
            responses=[
#                httpretty.Response(body=asgs_for_worker_before),
                httpretty.Response(body=asgs_for_worker_after),
                ],
        )

        # Mock endpoints for building new ASGs
        task_url = "http://some.host/task/new_asg_1234.json"
        def new_asg_post_callback(request, uri, headers):
            response_headers = { "Location": task_url,
                    "server": ASGARD_API_ENDPOINT}
            response_body = ""
            new_asg_name = "{}-v099".format(request.parsed_body["name"][0])
            new_ami_id = request.parsed_body["imageId"][0]
            create_asg_with_tags(new_asg_name, asg_tags, new_ami_id)
            return (302, response_headers, response_body)

        httpretty.register_uri(
                httpretty.POST,
                NEW_ASG_URL,
                body=new_asg_post_callback,
                Location=task_url)

        httpretty.register_uri(
            httpretty.GET,
            task_url,
            body=new_asg_task_status,
            content_type="application/json")

        # Make endpoint for enabling new ASGs
        enable_asg_task_url = "http://some.host/task/enable_asg_1234.json"
        def enable_asg_post_callback(request, uri, headers):
            response_headers = { "Location": enable_asg_task_url,
                    "server": ASGARD_API_ENDPOINT}
            response_body = ""
            return (302, response_headers, response_body)

        disable_asg_task_url = "http://some.host/task/disable_asg_1234.json"
        def disable_asg_post_callback(request, uri, headers):
            response_headers = { "Location": disable_asg_task_url,
                    "server": ASGARD_API_ENDPOINT}
            response_body = ""
            return (302, response_headers, response_body)

        httpretty.register_uri(
                httpretty.POST,
                ASG_ACTIVATE_URL,
                body=enable_asg_post_callback)

        httpretty.register_uri(
                httpretty.POST,
                ASG_DEACTIVATE_URL,
                body=disable_asg_post_callback)

        httpretty.register_uri(
            httpretty.GET,
            disable_asg_task_url,
            body=disable_asg_task_status,
            content_type="application/json")

        httpretty.register_uri(
            httpretty.GET,
            enable_asg_task_url,
            body=enable_asg_task_status,
            content_type="application/json")

        asg_info_url = ASG_INFO_URL.format("loadtest-edx-edxapp-v099")
        httpretty.register_uri(
            httpretty.GET,
            asg_info_url,
            body=sample_asg_info,
            content_type="application/json")

        worker_asg_info_url = ASG_INFO_URL.format("loadtest-edx-worker-v099")
        httpretty.register_uri(
            httpretty.GET,
            worker_asg_info_url,
            body=sample_worker_asg_info,
            content_type="application/json")

        return ami_id

    @httpretty.activate
    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_deploy_asg_failed(self):
        ami_id = self._setup_for_deploy(
                new_asg_task_status=failed_sample_task
        )
        self.assertRaises(Exception, deploy, ami_id)

    @httpretty.activate
    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_deploy_enable_asg_failed(self):
        ami_id = self._setup_for_deploy(
                new_asg_task_status=completed_sample_task,
                enable_asg_task_status=failed_sample_task)
        self.assertRaises(Exception, deploy, ami_id)

    @httpretty.activate
    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_deploy_elb_health_failed(self):
        ami_id = self._setup_for_deploy(completed_sample_task, completed_sample_task)
        mock_function = "tubular.ec2.wait_for_healthy_elbs"
        with mock.patch(mock_function, side_effect=Exception("Never became healthy.")):
            self.assertRaises(Exception, deploy, ami_id)

    @httpretty.activate
    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_deploy_asg_being_deleted(self):
        ami_id = self._setup_for_deploy(

    @httpretty.activate
    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_deploy(self):
        ami_id = self._setup_for_deploy()
        self.assertEquals(None, deploy(ami_id))
