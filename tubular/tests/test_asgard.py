"""
Tests of the code interacting with the Asgard API.
"""

import os
import unittest
import itertools
import boto3
import mock
import requests_mock

from ddt import ddt, data, unpack
from moto import mock_ec2, mock_autoscaling, mock_elb
from moto.ec2.utils import random_ami_id
from six.moves import urllib, reload_module
import tubular.asgard as asgard
from tubular.exception import (
    BackendError,
    CannotDeleteActiveASG,
    CannotDeleteLastASG,
    ASGDoesNotExistException,
    RateLimitedException
)
from tubular.tests.test_utils import create_asg_with_tags, create_elb
from tubular.ec2 import tag_asg_for_deletion

# Disable the retry decorator and reload the asgard module. This will ensure that tests do not fail because of the retry
# decorator recalling a method when using httpretty with side effect iterators
os.environ['TUBULAR_RETRY_ENABLED'] = "false"
os.environ['RETRY_MAX_ATTEMPTS'] = "1"
reload_module(asgard)  # pylint: disable=too-many-function-args

SAMPLE_CLUSTER_LIST = [
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
]

BAD_CLUSTER_JSON1 = """
<HTML><HEAD>Have some HTML</HEAD></HTML>
"""

BAD_CLUSTER_JSON2 = [
    {
        "autoScalingGroups":
            [
                "loadtest-edx-edxapp-v058",
                "loadtest-edx-edxapp-v059"
            ]
    }
]

HTML_RESPONSE_BODY = "<html>This is not JSON...</html>"

VALID_CLUSTER_JSON_INFO = [
    {
        "autoScalingGroupName": "loadtest-edx-edxapp-v058",
        "availabilityZones":
            [
                "us-east-1b",
                "us-east-1c"
            ],
        "createdTime": "2016-02-10T12:23:10Z",
        "defaultCooldown": 300,
        "desiredCapacity": 4,
        "minSize": 4
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
        "desiredCapacity": 4,
        "minSize": 4
    }
]

VALID_SINGLE_ASG_CLUSTER_INFO_JSON = [
    {
        "autoScalingGroupName": "loadtest-edx-edxapp-v060",
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

ASGS_FOR_EDXAPP_BEFORE = [
    {
        "autoScalingGroupName": "loadtest-edx-edxapp-v058",
        "desiredCapacity": 4,
        "minSize": 4,
        "maxSize": 4
    },
    {
        "autoScalingGroupName": "loadtest-edx-edxapp-v059",
        "desiredCapacity": 4,
        "minSize": 4,
        "maxSize": 4
    }
]

ASGS_FOR_EDXAPP_AFTER = [
    {
        "autoScalingGroupName": "loadtest-edx-edxapp-v058",
        "desiredCapacity": 0,
        "minSize": 0,
        "maxSize": 0
    },
    {
        "autoScalingGroupName": "loadtest-edx-edxapp-v059",
        "desiredCapacity": 4,
        "minSize": 4,
        "maxSize": 4
    },
    {
        "autoScalingGroupName": "loadtest-edx-edxapp-v099",
        "desiredCapacity": 4,
        "minSize": 4,
        "maxSize": 4
    }
]

ASGS_FOR_WORKER_BEFORE = [
    {
        "autoScalingGroupName": "loadtest-edx-worker-v034",
        "maxSize": 1,
        "minSize": 1,
        "desiredCapacity": 1
    }
]
ASGS_FOR_WORKER_AFTER = [
    {
        "autoScalingGroupName": "loadtest-edx-worker-v034",
        "desiredCapacity": 0,
        "minSize": 0,
        "maxSize": 0
    },
    {
        "autoScalingGroupName": "loadtest-edx-worker-v099",
        "desiredCapacity": 4,
        "minSize": 4,
        "maxSize": 4
    }
]


def deleted_asg_in_progress(name):
    """ Return an Asgard response for an asg that is being deleted. """
    return {
        "group": {
            "autoScalingGroupName": name,
            "loadBalancerNames":
                [
                    "app_elb"
                ],
            "status": "deleted",
            "launchingSuspended": False,
            "desiredCapacity": 4,
            "minSize": 4
        },
        "clusterName": "app_cluster"
    }


def deleted_asg_not_in_progress(name):
    """ Return an Asgard response for an asg that is finished being deleted. """
    return {
        "group": {
            "autoScalingGroupName": name,
            "loadBalancerNames": [
                "app_elb"
            ],
            "status": None,
            "desiredCapacity": 4,
            "minSize": 4,
            "launchingSuspended": True
        },
        "clusterName": "app_cluster"
    }


def disabled_asg(name):
    """ Return an Asgard response for an asg that is disabled. """
    return {
        "group": {
            "autoScalingGroupName": name,
            "loadBalancerNames": [
                "app_elb"
            ],
            "desiredCapacity": 0,
            "minSize": 0,
            "status": None,
            "launchingSuspended": True
        },
        "clusterName": "app_cluster"
    }


def enabled_asg(name):
    """ Return an Asgard response for an asg that is enabled. """
    return {
        "group": {
            "autoScalingGroupName": name,
            "loadBalancerNames": [
                "app_elb"
            ],
            "desiredCapacity": 4,
            "minSize": 4,
            "status": None,
            "launchingSuspended": False
        },
        "clusterName": "app_cluster"
    }


FAILED_SAMPLE_TASK = {
    "log":
        [
            "2016-02-11_02:31:18 Started on thread Task:Force Delete Auto Scaling Group 'loadtest-edx-edxapp-v060'.",
            "2016-02-11_02:31:18 Deregistering all instances in 'loadtest-edx-edxapp-v060' from load balancers",
            "2016-02-11_02:31:18 Deregister all instances in Auto Scaling Group 'loadtest-edx-edxapp-v060' from ELBs",
            "2016-02-11_02:31:19 Deleting auto scaling group 'loadtest-edx-edxapp-v060'",
            "2016-02-11_02:31:19 Delete Auto Scaling Group 'loadtest-edx-edxapp-v060'",
            "2016-02-11_02:31:19 Auto scaling group 'loadtest-edx-edxapp-v060' will be deleted after deflation "
            "finishes",
            (
                "2016-02-11_02:41:24 Exception: com.netflix.asgard.push.PushException: Timeout waiting "
                "10m for auto scaling group 'loadtest-edx-edxapp-v060' to disappear from AWS."
            )
        ],
    "status": "failed",
    "operation": "",
    "durationString": "10m 6s",
    "updateTime": "2016-02-11 02:41:24 UTC"
}

COMPLETED_SAMPLE_TASK = {
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

RUNNING_SAMPLE_TASK = {
    "log":
        [
            (
                "2016-02-11_19:03:34 Started on thread Task:Creating auto scaling group 'loadtest-edx-edxapp-v059', "
                "min 4, max 4, traffic prevented."
            ),
            "2016-02-11_19:03:34 Group 'loadtest-edx-edxapp-v059' will start with 0 instances",
            "2016-02-11_19:03:34 Create Auto Scaling Group 'loadtest-edx-edxapp-v059'",
            (
                "2016-02-11_19:03:34 Create Launch Configuration 'loadtest-edx-edxapp-v059-20160211190334' "
                "with image 'ami-f2032998'"
            ),
            "2016-02-11_19:03:35 Create Autoscaling Group 'loadtest-edx-edxapp-v059'",
            "2016-02-11_19:03:35 Disabling adding instances to ELB for auto scaling group 'loadtest-edx-edxapp-v059'",
            (
                "2016-02-11_19:03:35 Launch Config 'loadtest-edx-edxapp-v059-20160211190334' has been created. "
                "Auto Scaling Group 'loadtest-edx-edxapp-v059' has been created. "
            ),
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

AWS_RATE_LIMIT_EXCEPTION = {
    "log":
        [
            (
                "2017-10-18_16:14:34 Started on thread Task:Creating auto scaling group "
                "'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271', min 15, max 15, traffic prevented."
            ),
            "2017-10-18_16:14:34 Group 'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271' will start with 0 "
            "instances",
            "2017-10-18_16:14:34 Create Auto Scaling Group 'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271'",
            ("2017-10-18_16:14:34 Create Launch Configuration "
             "'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271-20171018161434' with image 'ami-abbf6fd1'"),
            "2017-10-18_16:14:34 Create Autoscaling Group 'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271'",
            ("2017-10-18_16:14:35 Disabling adding instances "
             "to ELB for auto scaling group 'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271'"),
            (
                "2017-10-18_16:14:35 Launch Config "
                "'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271-20171018161434' has been created. "
                "Auto Scaling Group 'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271' has been created. "
            ),
            '2017-10-18_16:14:35 Create 2 Scaling Policies',
            "2017-10-18_16:14:35 Create Scaling Policy 'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271-1779'",
            "2017-10-18_16:14:35 Create Alarm 'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271-1779'",
            "2017-10-18_16:14:36 Create Scaling Policy 'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271-1780'",
            "2017-10-18_16:14:36 Create Alarm 'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271-1780'",
            "2017-10-18_16:14:36 Resizing group 'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271' to min 15,"
            " max 15",
            "2017-10-18_16:14:36 Setting group 'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271' to min 15 max 15",
            "2017-10-18_16:14:36 Update Autoscaling Group 'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271'",
            ("2017-10-18_16:14:36 Group 'stage-mckinsey-EdxappServerAsGroup-BX9JH5ALH5PD-v271'"
             " has 0 instances. Waiting for 15 to exist."),
            (
                '2017-10-18_16:19:11 Exception: com.amazonaws.AmazonServiceException: Rate exceeded (Service: '
                'AmazonAutoScaling; Status Code: 400; Error Code: '
                'Throttling; Request ID: 1324046b-b420-11e7-a9eb-7fe7ac63f645)'
            )
        ],
    "status": "failed",
    "operation": "",
    "durationString": "0s",
    "updateTime": "2016-02-11 02:31:12 UTC"
}

SAMPLE_ASG_INFO = {
    "group": {
        "loadBalancerNames":
            [
                "app_elb"
            ],
        "desiredCapacity": 4,
        "minSize": 4
    }
}

SAMPLE_WORKER_ASG_INFO = {
    "group": {
        "loadBalancerNames": [],
        "desiredCapacity": 4,
        "minSize": 4
    }
}


@ddt
@requests_mock.Mocker()
class TestAsgard(unittest.TestCase):
    """
    Class containing all Asgard tests.
    """
    _multiprocess_can_split_ = True

    def test_bad_clusters_endpoint(self, _req_mock):
        relevant_asgs = []
        self.assertRaises(requests_mock.NoMockAddress, asgard.clusters_for_asgs, relevant_asgs)

    def test_clusters_for_asgs(self, req_mock):
        req_mock.get(
            asgard.CLUSTER_LIST_URL,
            json=SAMPLE_CLUSTER_LIST)

        relevant_asgs = []
        cluster_names = asgard.clusters_for_asgs(relevant_asgs)
        self.assertEqual({}, cluster_names)

        relevant_asgs = ["loadtest-edx-edxapp-v058"]
        expected_clusters = {
            "loadtest-edx-edxapp": ["loadtest-edx-edxapp-v058", "loadtest-edx-edxapp-v059"]
        }
        cluster_names = asgard.clusters_for_asgs(relevant_asgs)
        self.assertEqual(expected_clusters, cluster_names)

        relevant_asgs = ["loadtest-edx-edxapp-v058", "loadtest-edx-worker-v034"]
        cluster_names = asgard.clusters_for_asgs(relevant_asgs)
        self.assertIn("loadtest-edx-edxapp", cluster_names)
        self.assertIn("loadtest-edx-worker", cluster_names)
        self.assertEqual(["loadtest-edx-worker-v034"], cluster_names['loadtest-edx-worker'])
        self.assertEqual(
            ["loadtest-edx-edxapp-v058", "loadtest-edx-edxapp-v059"],
            cluster_names['loadtest-edx-edxapp']
        )

    def test_clusters_for_asgs_bad_response(self, req_mock):
        req_mock.get(
            asgard.CLUSTER_LIST_URL,
            text=HTML_RESPONSE_BODY)

        relevant_asgs = []
        with self.assertRaises(BackendError):
            __ = asgard.clusters_for_asgs(relevant_asgs)

    @data(BAD_CLUSTER_JSON1, BAD_CLUSTER_JSON2)
    def test_incorrect_json(self, response_json, req_mock):
        # The json is valid but not the structure we expected.
        req_mock.get(
            asgard.CLUSTER_LIST_URL,
            json=response_json)

        relevant_asgs = []
        self.assertRaises(BackendError, asgard.clusters_for_asgs, relevant_asgs)

    def test_asg_for_cluster(self, req_mock):
        cluster = "prod-edx-edxapp"
        url = asgard.CLUSTER_INFO_URL.format(cluster)
        req_mock.get(
            url,
            json=VALID_CLUSTER_JSON_INFO)

        expected_asgs = ["loadtest-edx-edxapp-v058", "loadtest-edx-edxapp-v059"]
        returned_asgs = [asg['autoScalingGroupName'] for asg in asgard.asgs_for_cluster(cluster)]
        self.assertEqual(expected_asgs, returned_asgs)

    def test_asg_for_cluster_bad_response(self, req_mock):
        cluster = "prod-edx-edxapp"
        url = asgard.CLUSTER_INFO_URL.format(cluster)
        req_mock.get(
            url,
            text=HTML_RESPONSE_BODY)

        expected_asgs = ["loadtest-edx-edxapp-v058", "loadtest-edx-edxapp-v059"]
        with self.assertRaises(BackendError):
            self.assertEqual(expected_asgs, asgard.asgs_for_cluster(cluster))

    def test_bad_asgs_endpoint(self, _req_mock):
        cluster = "Fake cluster"
        self.assertRaises(requests_mock.NoMockAddress, asgard.asgs_for_cluster, cluster)

    def test_asg_for_cluster_incorrect_json(self, req_mock):
        cluster = "prod-edx-edxapp"
        url = asgard.CLUSTER_INFO_URL.format(cluster)
        req_mock.get(
            url,
            text=BAD_CLUSTER_JSON1,
            headers={'Content-Type': 'application/json'})

        self.assertRaises(BackendError, asgard.asgs_for_cluster, cluster)

    def test_elbs_for_asg(self, req_mock):
        asg_info_url = asgard.ASG_INFO_URL.format("test_asg")
        req_mock.get(
            asg_info_url,
            json=SAMPLE_ASG_INFO)

        self.assertEqual(asgard.elbs_for_asg("test_asg"), ["app_elb"])

    def test_elbs_for_asg_bad_data(self, req_mock):
        asg_info_url = asgard.ASG_INFO_URL.format("test_asg")
        req_mock.get(
            asg_info_url,
            text=HTML_RESPONSE_BODY)

        self.assertRaises(BackendError, asgard.elbs_for_asg, "test_asg")

    def test_elbs_for_asg_bad_response(self, req_mock):
        asg_info_url = asgard.ASG_INFO_URL.format("test_asg")
        req_mock.get(
            asg_info_url,
            text=BAD_CLUSTER_JSON1,
            headers={'Content-Type': 'application/json'})

        self.assertRaises(BackendError, asgard.elbs_for_asg, "test_asg")

    def test_bad_asg_info_endpoint(self, _req_mock):
        self.assertRaises(requests_mock.NoMockAddress, asgard.elbs_for_asg, "fake_asg")

    def test_task_completion(self, req_mock):
        task_url = "http://some.host/task/1234.json"
        req_mock.get(
            task_url,
            json=COMPLETED_SAMPLE_TASK)

        actual_output = asgard.wait_for_task_completion(task_url, 1)
        expected_output = COMPLETED_SAMPLE_TASK
        self.assertEqual(expected_output, actual_output)

    def test_failed_task_completion(self, req_mock):
        task_url = "http://some.host/task/1234.json"
        req_mock.get(
            task_url,
            json=FAILED_SAMPLE_TASK)

        actual_output = asgard.wait_for_task_completion(task_url, 1)
        expected_output = FAILED_SAMPLE_TASK
        self.assertEqual(expected_output, actual_output)

    def test_running_then_failed_task_completion(self, req_mock):
        task_url = "http://some.host/task/1234.json"
        req_mock.get(
            task_url,
            [
                dict(json=RUNNING_SAMPLE_TASK),
                dict(json=FAILED_SAMPLE_TASK),
            ])

        with mock.patch('tubular.asgard.WAIT_SLEEP_TIME', 1):
            actual_output = asgard.wait_for_task_completion(task_url, 2)
            expected_output = FAILED_SAMPLE_TASK
            self.assertEqual(expected_output, actual_output)

    def test_task_completion_bad_response(self, req_mock):
        task_url = "http://some.host/task/1234.json"
        req_mock.get(
            task_url,
            text=HTML_RESPONSE_BODY)

        with self.assertRaises(BackendError):
            asgard.wait_for_task_completion(task_url, 1)

    def test_new_asg_aws_rate_limit(self, req_mock):
        task_url = "http://some.host/task/1234.json"
        cluster = "loadtest-edx-edxapp"
        ami_id = "ami-abc1234"

        req_mock.post(
            asgard.NEW_ASG_URL,
            headers={"Location": task_url},
            status_code=200)

        req_mock.get(
            asgard.NEW_ASG_URL,
            json=AWS_RATE_LIMIT_EXCEPTION,
            headers={"Location": task_url},
            status_code=200)

        url = asgard.CLUSTER_INFO_URL.format(cluster)
        req_mock.get(
            url,
            json=VALID_CLUSTER_JSON_INFO)
        self.assertRaises(RateLimitedException, asgard.new_asg, cluster, ami_id)

    def test_new_asg(self, req_mock):
        task_url = "http://some.host/task/1234.json"
        cluster = "loadtest-edx-edxapp"
        ami_id = "ami-abc1234"

        def post_callback(request, context):
            """
            Callback method for POST.
            """
            self.assertEqual('POST', request.method)
            expected_request_body = {"name": [cluster], "imageId": [ami_id]}
            expected_querystring = {"asgardApiToken": ['dummy-token']}

            parsed_body = urllib.parse.parse_qs(request.text)
            parsed_query = urllib.parse.parse_qs(
                urllib.parse.urlparse(request.url).query
            )
            self.assertEqual(expected_request_body, parsed_body)
            self.assertEqual(expected_querystring, parsed_query)
            context.headers = {
                "Location": task_url,
                "server": asgard.ASGARD_API_ENDPOINT
            }
            context.status_code = 302
            return ""

        req_mock.post(
            asgard.NEW_ASG_URL,
            json=post_callback,
            headers={"Location": task_url})

        req_mock.get(
            task_url,
            json=COMPLETED_SAMPLE_TASK)

        url = asgard.CLUSTER_INFO_URL.format(cluster)
        req_mock.get(
            url,
            json=VALID_CLUSTER_JSON_INFO)

        expected_asg = "loadtest-edx-edxapp-v059"
        self.assertEqual(expected_asg, asgard.new_asg(cluster, ami_id))

    @data(
        ("http://some.host/task/1234.json",  # task to deploy a cluster failed.
         302,
         {"server": asgard.ASGARD_API_ENDPOINT},
         "",
         FAILED_SAMPLE_TASK,
         200,
         VALID_CLUSTER_JSON_INFO,
         BackendError
         ),
        ("http://some.host/task/1234.json",  # Cluster not found after creation
         302,
         {"server": asgard.ASGARD_API_ENDPOINT},
         "",
         FAILED_SAMPLE_TASK,
         404,
         VALID_CLUSTER_JSON_INFO,
         BackendError
         ),
        ("http://some.host/task/1234.json",  # Task creation failed
         500,
         {"server": asgard.ASGARD_API_ENDPOINT},
         "",
         FAILED_SAMPLE_TASK,
         200,
         VALID_CLUSTER_JSON_INFO,
         BackendError
         ),
        ("http://some.host/task/1234.json",  # failed to create ASG
         404,
         {"server": asgard.ASGARD_API_ENDPOINT},
         "",
         FAILED_SAMPLE_TASK,
         200,
         VALID_CLUSTER_JSON_INFO,
         BackendError
         ),
    )
    @unpack
    def test_new_asg_failure(self,
                             task_url,
                             create_response_code,
                             create_response_headers,
                             create_response_body,
                             task_response_body,
                             cluster_response_code,
                             cluster_response_body,
                             expected_exception,
                             req_mock):
        cluster = "loadtest-edx-edxapp"
        ami_id = "ami-abc1234"

        def post_callback(request, context):
            """
            Callback method for POST.
            """
            self.assertEqual('POST', request.method)
            expected_request_body = {"name": [cluster], "imageId": [ami_id]}
            expected_querystring = {"asgardApiToken": ['dummy-token']}

            parsed_body = urllib.parse.parse_qs(request.text)
            parsed_query = urllib.parse.parse_qs(
                urllib.parse.urlparse(request.url).query
            )
            self.assertEqual(expected_request_body, parsed_body)
            self.assertEqual(expected_querystring, parsed_query)
            context.status_code = create_response_code
            context.headers.update(create_response_headers)
            return create_response_body

        req_mock.post(
            asgard.NEW_ASG_URL,
            json=post_callback,
            headers={"Location": task_url})

        # Mock 'Task' response
        req_mock.get(
            task_url,
            json=task_response_body)

        # Mock 'Cluster' response
        url = asgard.CLUSTER_INFO_URL.format(cluster)
        req_mock.get(
            url,
            status_code=cluster_response_code,
            json=cluster_response_body)

        self.assertRaises(expected_exception, asgard.new_asg, cluster, ami_id)

    def test_new_asg_404(self, req_mock):
        cluster = "loadtest-edx-edxapp"
        ami_id = "ami-abc1234"

        def post_callback(request, context):  # pylint: disable=unused-argument
            """
            Callback method for POST.
            """
            context.headers = {"server": asgard.ASGARD_API_ENDPOINT}
            context.status_code = 404
            return ""

        req_mock.post(
            asgard.NEW_ASG_URL,
            json=post_callback,
        )

        self.assertRaises(BackendError, asgard.new_asg, cluster, ami_id)

    def test_disable_asg_pending_deletion(self, req_mock):  # pylint: disable=unused-argument
        """
        Tests an ASG disable that is cancelled due to the ASG pending deletion.
        """

        def post_callback(request, context):  # pylint: disable=unused-argument
            """
            Callback method for POST.
            """
            # If this POST callback gets called, test has failed.
            raise Exception("POST called to disable ASG when it should have been skipped.")

        req_mock.post(
            asgard.ASG_DEACTIVATE_URL,
            json=post_callback
        )

        # setup the mocking of the is asg pending delete calls
        asg = 'loadtest-edx-edxapp-v059'
        self._mock_asgard_pending_delete(req_mock, [asg])
        self.assertTrue(asgard.is_asg_pending_delete(asg))

        self.assertEqual(None, asgard.disable_asg(asg))

    def test_disable_asg_does_not_exist(self, req_mock):  # pylint: disable=unused-argument
        def post_callback(request, context):  # pylint: disable=unused-argument
            """
            Callback method for POST.
            """
            # If this POST callback gets called, test has failed.
            raise Exception("POST called to disable ASG when it should have been skipped.")

        req_mock.post(
            asgard.ASG_DEACTIVATE_URL,
            json=post_callback
        )

        asg = 'loadtest-edx-edxapp-v059'
        self._mock_asgard_pending_delete(req_mock, [asg], 404)
        self.assertEqual(None, asgard.disable_asg(asg))

    @data((COMPLETED_SAMPLE_TASK, True), (FAILED_SAMPLE_TASK, False))
    @unpack
    def test_delete_asg(self, task_body, should_succeed, req_mock):
        asg = "loadtest-edx-edxapp-v060"
        cluster = "app_cluster"
        self._mock_asgard_not_pending_delete(req_mock, [asg])

        task_url = "http://some.host/task/1234.json"

        def post_callback(request, context):
            """
            Callback method for POST.
            """
            self.assertEqual('POST', request.method)
            expected_request_body = {"name": [asg]}
            expected_querystring = {"asgardApiToken": ['dummy-token']}

            parsed_body = urllib.parse.parse_qs(request.text)
            parsed_query = urllib.parse.parse_qs(
                urllib.parse.urlparse(request.url).query
            )
            self.assertEqual(expected_request_body, parsed_body)
            self.assertEqual(expected_querystring, parsed_query)
            context.headers = {"Location": task_url,
                               "Server": asgard.ASGARD_API_ENDPOINT}
            context.status_code = 302

            return ""

        req_mock.post(
            asgard.ASG_DELETE_URL,
            json=post_callback
        )

        req_mock.get(
            task_url,
            json=task_body
        )

        req_mock.get(
            asgard.CLUSTER_INFO_URL.format(cluster),
            json=VALID_CLUSTER_JSON_INFO
        )

        if should_succeed:
            self.assertEqual(None, asgard.delete_asg(asg, False))
        else:
            self.assertRaises(BackendError, asgard.delete_asg, asg, False)

    def test_delete_asg_active(self, req_mock):
        asg = "loadtest-edx-edxapp-v060"
        self._mock_asgard_not_pending_delete(req_mock, [asg], json_builder=enabled_asg)

        def post_callback(request, context):  # pylint: disable=unused-argument
            """
            Callback method for POST.
            """
            raise Exception("This post should not be called")

        req_mock.post(
            asgard.ASG_DELETE_URL,
            json=post_callback
        )

        with mock.patch("tubular.ec2.remove_asg_deletion_tag"):
            self.assertRaises(CannotDeleteActiveASG, asgard.delete_asg, asg, True)

    def test_delete_asg_pending_delete(self, req_mock):
        asg = "loadtest-edx-edxapp-v060"
        self._mock_asgard_pending_delete(req_mock, [asg])
        self.assertEqual(None, asgard.delete_asg(asg, True))

    def test_delete_last_asg(self, req_mock):
        asg = "loadtest-edx-edxapp-v060"
        cluster = "app_cluster"
        self._mock_asgard_not_pending_delete(req_mock, [asg], json_builder=disabled_asg)

        req_mock.get(
            asgard.ASG_INFO_URL.format(asg),
            json=disabled_asg(asg)
        )

        req_mock.get(
            asgard.CLUSTER_INFO_URL.format(cluster),
            json=VALID_SINGLE_ASG_CLUSTER_INFO_JSON
        )

        with mock.patch("tubular.ec2.remove_asg_deletion_tag"):
            self.assertRaises(CannotDeleteLastASG, asgard.delete_asg, asg)

    @mock_autoscaling
    @mock_ec2
    @data(*itertools.product(
        ((asgard.ASG_ACTIVATE_URL, asgard.enable_asg), (asgard.ASG_DEACTIVATE_URL, asgard.disable_asg)),
        (True, False)
    ))
    @unpack
    def test_enable_disable_asg(self, url_and_function, success, req_mock):
        """
        Tests enabling and disabling ASGs, with both success and failure.
        """
        endpoint_url, test_function = url_and_function
        task_url = "http://some.host/task/1234.json"
        asg = "loadtest-edx-edxapp-v059"
        cluster = "app_cluster"

        def post_callback(request, context):
            """
            Callback method for POST.
            """
            self.assertEqual('POST', request.method)
            expected_request_body = {"name": [asg]}
            expected_querystring = {"asgardApiToken": ['dummy-token']}

            parsed_body = urllib.parse.parse_qs(request.text)
            parsed_query = urllib.parse.parse_qs(
                urllib.parse.urlparse(request.url).query
            )
            self.assertEqual(expected_request_body, parsed_body)
            self.assertEqual(expected_querystring, parsed_query)
            context.headers = {
                "Location": task_url,
                "server": asgard.ASGARD_API_ENDPOINT
            }
            context.status_code = 302
            return ""

        req_mock.post(
            endpoint_url,
            json=post_callback
        )

        req_mock.get(
            asgard.ASG_INFO_URL.format(asg),
            json=enabled_asg(asg)
        )

        req_mock.get(
            asgard.CLUSTER_INFO_URL.format(cluster),
            json=VALID_CLUSTER_JSON_INFO
        )

        req_mock.get(
            task_url,
            json=COMPLETED_SAMPLE_TASK if success else FAILED_SAMPLE_TASK
        )

        url = asgard.ASG_INFO_URL.format(asg)
        req_mock.get(
            url,
            json=deleted_asg_not_in_progress(asg))

        if success:
            self.assertEqual(None, test_function(asg))
        else:
            self.assertRaises(BackendError, test_function, asg)

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_deploy_asg_error_did_not_create_multiple_asgs(self, req_mock):
        """
        Test that new_asg is not called more than the number of asgs that
        are intended to be created when an error occurs
        """
        counter = 0

        def count_new_asg_calls(request, context):
            """
            Count the number of times the new_asg request goes out
            """
            task_url = "http://some.host/task/new_asg_1234.json"
            context.headers = {
                "Location": task_url,
                "server": asgard.ASGARD_API_ENDPOINT
            }
            request_values = urllib.parse.parse_qs(request.text)
            new_asg_name = "{}-v099".format(request_values["name"][0])
            new_ami_id = request_values["imageId"][0]
            create_asg_with_tags(new_asg_name, self.test_asg_tags, new_ami_id)
            context.status_code = 302
            nonlocal counter
            counter = counter + 1
            return ""

        ami_id = self._setup_for_deploy(
            req_mock,
            new_asg_task_status=FAILED_SAMPLE_TASK,
            new_asg_post_callback_override=count_new_asg_calls
        )

        try:
            asgard.deploy(ami_id)
        except BackendError:
            pass
        self.assertEqual(1, counter)  # We fail midway here, so we dont expect additional calls to new_asg

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_deploy_asg_rate_limit_did_not_create_multiple_asgs(self, req_mock):
        """
        Test that new_asg is not called more than the number of asgs that are
        intended to be created when AWS throttles our requests
        """
        counter = 0

        def count_new_asg_calls(request, context):
            """
            Count the number of times the new_asg request goes out
            """
            task_url = "http://some.host/task/new_asg_1234.json"
            context.headers = {
                "Location": task_url,
                "server": asgard.ASGARD_API_ENDPOINT
            }
            request_values = urllib.parse.parse_qs(request.text)
            new_asg_name = "{}-v099".format(request_values["name"][0])
            new_ami_id = request_values["imageId"][0]
            create_asg_with_tags(new_asg_name, self.test_asg_tags, new_ami_id)
            context.status_code = 302
            nonlocal counter
            counter = counter + 1
            return ""

        ami_id = self._setup_for_deploy(req_mock, new_asg_post_callback_override=count_new_asg_calls)

        not_in_service_asgs = ["loadtest-edx-edxapp-v058"]
        in_service_asgs = ["loadtest-edx-edxapp-v059", "loadtest-edx-worker-v034"]
        new_asgs = ["loadtest-edx-edxapp-v099", "loadtest-edx-worker-v099"]

        self._mock_asgard_not_pending_delete(req_mock, in_service_asgs, json_builder=enabled_asg)
        self._mock_asgard_pending_delete(req_mock, not_in_service_asgs)

        for asg in new_asgs:
            url = asgard.ASG_INFO_URL.format(asg)
            req_mock.get(
                url,
                [
                    dict(json=deleted_asg_not_in_progress(asg),
                         status_code=200),
                    dict(json=deleted_asg_not_in_progress(asg),
                         status_code=200),
                    dict(json=AWS_RATE_LIMIT_EXCEPTION,
                         status_code=200),
                ])
        try:
            asgard.deploy(ami_id)
        except RateLimitedException:  # expect this failure to be bubbled up after failing MAX_RETRY times
            pass

        self.assertEqual(2, counter)  # once per new asg

    def _setup_for_deploy(  # pylint: disable=dangerous-default-value
            self,
            req_mock,
            new_asg_task_status=COMPLETED_SAMPLE_TASK,
            enable_asg_task_status=COMPLETED_SAMPLE_TASK,
            disable_asg_task_status=COMPLETED_SAMPLE_TASK,
            new_asg_post_callback_override=None
    ):
        """
        Setup all the variables for an ASG deployment.
        """
        # Make the AMI
        ec2_client = boto3.client('ec2')
        response = ec2_client.run_instances(ImageId=random_ami_id(), MinCount=1, MaxCount=1)
        instance_id = response['Instances'][0]['InstanceId']
        ami_name = 'fake-ami-for-testing'
        ami_description = 'This is a fake AMI created for testing purposes'
        response = ec2_client.create_image(
            InstanceId=instance_id, Name=ami_name,
            Description=ami_description, NoReboot=True
        )
        ami_id = response['ImageId']
        ec2_client.create_tags(
            Resources=[ami_id], Tags=[
                {'Key': 'environment', 'Value': 'foo'},
                {'Key': 'deployment', 'Value': 'bar'},
                {'Key': 'play', 'Value': 'baz'}
            ]
        )

        self.test_asg_tags = {
            "environment": "foo",
            "deployment": "bar",
            "play": "baz",
        }


        self.test_elb_name = "app_elb"
        create_elb(self.test_elb_name)

        create_asg_with_tags("loadtest-edx-edxapp-v058", self.test_asg_tags, ami_id, [self.test_elb_name])
        create_asg_with_tags("loadtest-edx-edxapp-v059", self.test_asg_tags, ami_id, [self.test_elb_name])
        create_asg_with_tags("loadtest-edx-worker-v034", self.test_asg_tags, ami_id, [])

        req_mock.get(
            asgard.CLUSTER_LIST_URL,
            json=SAMPLE_CLUSTER_LIST)

        edxapp_cluster_info_url = asgard.CLUSTER_INFO_URL.format("loadtest-edx-edxapp")
        req_mock.get(
            edxapp_cluster_info_url,
            [
                # dict(json=ASGS_FOR_EDXAPP_BEFORE),
                dict(json=ASGS_FOR_EDXAPP_AFTER),
            ],
        )

        worker_cluster_info_url = asgard.CLUSTER_INFO_URL.format("loadtest-edx-worker")
        req_mock.get(
            worker_cluster_info_url,
            [
                # dict(json=ASGS_FOR_WORKER_BEFORE),
                dict(json=ASGS_FOR_WORKER_AFTER),
            ],
        )

        # Mock endpoints for building new ASGs
        task_url = "http://some.host/task/new_asg_1234.json"

        def default_new_asg_callback(request, context):
            """
            Callback method for POST.
            """
            task_url = "http://some.host/task/new_asg_1234.json"
            context.headers = {
                "Location": task_url,
                "server": asgard.ASGARD_API_ENDPOINT
            }
            request_values = urllib.parse.parse_qs(request.text)
            new_asg_name = "{}-v099".format(request_values["name"][0])
            new_ami_id = request_values["imageId"][0]
            create_asg_with_tags(new_asg_name, self.test_asg_tags, new_ami_id)
            context.status_code = 302
            return ""

        req_mock.post(
            asgard.NEW_ASG_URL,
            json=default_new_asg_callback if new_asg_post_callback_override is None else new_asg_post_callback_override)

        req_mock.get(
            task_url,
            json=new_asg_task_status)

        # Make endpoint for enabling new ASGs
        enable_asg_task_url = "http://some.host/task/enable_asg_1234.json"

        def enable_asg_post_callback(request, context):  # pylint: disable=unused-argument
            """
            Callback method for POST.
            """
            context.headers = {
                "Location": enable_asg_task_url,
                "server": asgard.ASGARD_API_ENDPOINT
            }
            context.status_code = 302
            return ""

        disable_asg_task_url = "http://some.host/task/disable_asg_1234.json"

        def disable_asg_post_callback(request, context):  # pylint: disable=unused-argument
            """
            Callback method for POST.
            """
            context.headers = {
                "Location": disable_asg_task_url,
                "server": asgard.ASGARD_API_ENDPOINT
            }
            context.status_code = 302
            return ""

        req_mock.post(
            asgard.ASG_ACTIVATE_URL,
            json=enable_asg_post_callback)

        req_mock.post(
            asgard.ASG_DEACTIVATE_URL,
            json=disable_asg_post_callback)

        req_mock.get(
            disable_asg_task_url,
            json=disable_asg_task_status)

        req_mock.get(
            enable_asg_task_url,
            json=enable_asg_task_status)

        return ami_id

    def _mock_asgard_not_pending_delete(
            self, req_mock, asgs, response_code=200, json_builder=deleted_asg_not_in_progress, html_return=False
    ):
        """
        This helper function will mock calls to the asgard api related to is_asg_pending_delete. The response will be
        that this ASG is not pending delete.

        Arguments:
            req_mock: A requests_mock Mocker()
            asgs(list<str>): a list of the ASG names that are being checked
            response_code(int): an HTML response code sent from Asgard
            body(str): Format string for JSON response
            html_return(boolean): If True, return HTML instead of JSON

        Returns:
            None
        """
        for asg in asgs:
            url = asgard.ASG_INFO_URL.format(asg)
            if html_return:
                req_mock.get(
                    url,
                    text=HTML_RESPONSE_BODY,
                    status_code=response_code)
            else:
                req_mock.get(
                    url,
                    json=json_builder(asg),
                    status_code=response_code)

    def _mock_asgard_pending_delete(self, req_mock, asgs, response_code=200):
        """
        This helper function will mock calls to the asgard api related to is_asg_pending_delete.  The response will be
        that this ASG is pending delete.

        Arguments:
            req_mock: A requests_mock Mocker()
            asgs(list<str>): a list of the ASG names that are being checked
            response_code(int): an HTML response code sent from Asgard

        Returns:
            None
        """
        for asg in asgs:
            url = asgard.ASG_INFO_URL.format(asg)
            req_mock.get(
                url,
                json=deleted_asg_in_progress(asg),
                status_code=response_code)

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_deploy_asg_failed(self, req_mock):
        ami_id = self._setup_for_deploy(
            req_mock,
            new_asg_task_status=FAILED_SAMPLE_TASK
        )
        self.assertRaises(Exception, asgard.deploy, ami_id)

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_deploy_enable_asg_failed(self, req_mock):
        ami_id = self._setup_for_deploy(
            req_mock,
            new_asg_task_status=COMPLETED_SAMPLE_TASK,
            enable_asg_task_status=FAILED_SAMPLE_TASK
        )
        self.assertRaises(Exception, asgard.deploy, ami_id)

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_deploy_elb_health_failed(self, req_mock):
        ami_id = self._setup_for_deploy(req_mock, COMPLETED_SAMPLE_TASK, COMPLETED_SAMPLE_TASK)
        mock_function = "tubular.ec2.wait_for_healthy_elbs"
        with mock.patch(mock_function, side_effect=Exception("Never became healthy.")):
            self.assertRaises(Exception, asgard.deploy, ami_id)

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_deploy(self, req_mock):
        ami_id = self._setup_for_deploy(req_mock)

        not_in_service_asgs = ["loadtest-edx-edxapp-v058"]
        in_service_asgs = ["loadtest-edx-edxapp-v059", "loadtest-edx-worker-v034"]
        new_asgs = ["loadtest-edx-edxapp-v099", "loadtest-edx-worker-v099"]

        self._mock_asgard_not_pending_delete(req_mock, in_service_asgs, json_builder=enabled_asg)
        self._mock_asgard_pending_delete(req_mock, not_in_service_asgs)

        cluster = "app_cluster"
        for asg in new_asgs:
            url = asgard.ASG_INFO_URL.format(asg)
            req_mock.get(
                url,
                [
                    dict(json=deleted_asg_not_in_progress(asg),
                         status_code=200),
                    dict(json=deleted_asg_not_in_progress(asg),
                         status_code=200),
                    dict(json=enabled_asg(asg),
                         status_code=200),
                ])

        req_mock.get(
            asgard.CLUSTER_INFO_URL.format(cluster),
            json=VALID_CLUSTER_JSON_INFO
        )
        expected_output = {
            'ami_id': ami_id,
            'current_ami_id': ami_id,
            'current_asgs':
                {
                    'loadtest-edx-edxapp': ['loadtest-edx-edxapp-v099'],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v099']
                },
            'disabled_ami_id': ami_id,
            'disabled_asgs':
                {
                    'loadtest-edx-edxapp':
                        [
                            'loadtest-edx-edxapp-v058',
                            'loadtest-edx-edxapp-v059'
                        ],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v034']
                }
        }

        self.assertEqual(expected_output, asgard.deploy(ami_id))

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_deploy_new_asg_disabled(self, req_mock):
        ami_id = self._setup_for_deploy(req_mock)
        asgs = ["loadtest-edx-edxapp-v058", "loadtest-edx-edxapp-v059",
                "loadtest-edx-edxapp-v099", "loadtest-edx-worker-v099"]
        for asg in asgs:
            url = asgard.ASG_INFO_URL.format(asg)
            req_mock.get(
                url,
                [
                    dict(json=deleted_asg_not_in_progress(asg),
                         status_code=200),
                    dict(json=deleted_asg_in_progress(asg),
                         status_code=200),
                    dict(json=disabled_asg(asg),
                         status_code=200)
                ]
            )
        self.assertRaises(BackendError, asgard.deploy, ami_id)

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_rollback(self, req_mock):
        ami_id = self._setup_for_deploy(req_mock)

        in_service_pre_rollback_asgs = [
            "loadtest-edx-edxapp-v099", "loadtest-edx-worker-v099"
        ]
        in_service_post_rollback_asgs = [
            "loadtest-edx-edxapp-v058", "loadtest-edx-edxapp-v059", "loadtest-edx-worker-v034"
        ]

        for asg in in_service_pre_rollback_asgs:
            url = asgard.ASG_INFO_URL.format(asg)
            req_mock.get(
                url,
                [
                    # Start enabled and finish disabled.
                    dict(json=enabled_asg(asg),
                         status_code=200),
                    dict(json=enabled_asg(asg),
                         status_code=200),
                    dict(json=disabled_asg(asg),
                         status_code=200),
                ]
            )
        for asg in in_service_post_rollback_asgs:
            url = asgard.ASG_INFO_URL.format(asg)
            req_mock.get(
                url,
                [
                    # Start disabled and finish enabled.
                    dict(json=disabled_asg(asg),
                         status_code=200),
                    dict(json=disabled_asg(asg),
                         status_code=200),
                    dict(json=enabled_asg(asg),
                         status_code=200),
                ]
            )
        cluster = "app_cluster"
        req_mock.get(
            asgard.CLUSTER_INFO_URL.format(cluster),
            json=VALID_CLUSTER_JSON_INFO
        )

        rollback_input = {
            'current_asgs': {
                'loadtest-edx-edxapp': ['loadtest-edx-edxapp-v099'],
                'loadtest-edx-worker': ['loadtest-edx-worker-v099']
            },
            'disabled_asgs': {
                'loadtest-edx-edxapp':
                    [
                        'loadtest-edx-edxapp-v058',
                        'loadtest-edx-edxapp-v059'
                    ],
                'loadtest-edx-worker': ['loadtest-edx-worker-v034']
            },
        }
        # The expected output is the rollback input with reversed current/disabled asgs.
        expected_output = {}
        expected_output['current_asgs'] = rollback_input['disabled_asgs']
        expected_output['disabled_asgs'] = rollback_input['current_asgs']
        expected_output['ami_id'] = ami_id
        expected_output['current_ami_id'] = ami_id
        expected_output['disabled_ami_id'] = ami_id

        # Rollback and check output.
        self.assertEqual(
            asgard.rollback(rollback_input['current_asgs'], rollback_input['disabled_asgs'], ami_id),
            expected_output
        )

    def _setup_rollback_deleted(self, req_mock):
        """
        Setup the scenario where an ASG deployment is rolled-back to a previous ASG.

        Args:
            not_in_service_deleted(bool): if set not_in_service_asgs will return a 404
        """
        # pylint: disable=attribute-defined-outside-init
        self.test_ami_id = self._setup_for_deploy(req_mock)

        not_in_service_asgs = ["loadtest-edx-edxapp-v058"]
        in_service_pre_rollback_asgs = ["loadtest-edx-edxapp-v059", "loadtest-edx-worker-v034"]
        self.rollback_to_asgs = ["loadtest-edx-edxapp-v097", "loadtest-edx-worker-v098"]
        in_service_post_rollback_asgs = ["loadtest-edx-edxapp-v099", "loadtest-edx-worker-v099"]

        # Create the "rollback-to" ASGs.
        for asg in self.rollback_to_asgs + not_in_service_asgs:
            url = asgard.ASG_INFO_URL.format(asg)
            req_mock.get(
                url,
                status_code=404,
                text=BAD_CLUSTER_JSON1,
                headers={'Content-Type': "text/html"})

        self._mock_asgard_not_pending_delete(req_mock, in_service_pre_rollback_asgs, json_builder=enabled_asg)

        for asg in in_service_post_rollback_asgs:
            url = asgard.ASG_INFO_URL.format(asg)
            req_mock.get(
                url,
                [
                    # Start disabled and end enabled.
                    dict(json=disabled_asg(asg),
                         status_code=200),
                    dict(json=disabled_asg(asg),
                         status_code=200),
                    dict(json=enabled_asg(asg),
                         status_code=200),
                ]
            )

        cluster = "app_cluster"
        req_mock.get(
            asgard.CLUSTER_INFO_URL.format(cluster),
            json=VALID_CLUSTER_JSON_INFO
        )

    def _setup_rollback(self, req_mock):
        """
        Setup the scenario where an ASG deployment is rolled-back to a previous ASG.
        """
        # pylint: disable=attribute-defined-outside-init
        self.test_ami_id = self._setup_for_deploy(req_mock)

        not_in_service_asgs = ["loadtest-edx-edxapp-v058"]
        in_service_pre_rollback_asgs = ["loadtest-edx-edxapp-v059", "loadtest-edx-worker-v034"]
        self.rollback_to_asgs = ["loadtest-edx-edxapp-v097", "loadtest-edx-worker-v098"]
        in_service_post_rollback_asgs = ["loadtest-edx-edxapp-v099", "loadtest-edx-worker-v099"]

        # Create the "rollback-to" ASGs.
        for asg in self.rollback_to_asgs:
            create_asg_with_tags(asg, self.test_asg_tags, self.test_ami_id, [self.test_elb_name])

        self._mock_asgard_not_pending_delete(req_mock, in_service_pre_rollback_asgs, json_builder=enabled_asg)
        self._mock_asgard_pending_delete(req_mock, not_in_service_asgs)

        for asg in in_service_post_rollback_asgs:
            url = asgard.ASG_INFO_URL.format(asg)
            req_mock.get(
                url,
                [
                    # Start disabled and end enabled.
                    dict(json=disabled_asg(asg),
                         status_code=200),
                    dict(json=disabled_asg(asg),
                         status_code=200),
                    dict(json=enabled_asg(asg),
                         status_code=200),
                ]
            )

        cluster = "app_cluster"
        req_mock.get(
            asgard.CLUSTER_INFO_URL.format(cluster),
            json=VALID_CLUSTER_JSON_INFO
        )

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_rollback_with_failure_and_with_redeploy(self, req_mock):
        self._setup_rollback(req_mock)

        # The pending delete of the ASGs to rollback to causes the rollback to fail.
        self._mock_asgard_pending_delete(req_mock, self.rollback_to_asgs)

        rollback_input = {
            'current_asgs': {
                'loadtest-edx-edxapp':
                    [
                        'loadtest-edx-edxapp-v058',
                        'loadtest-edx-edxapp-v059'
                    ],
                'loadtest-edx-worker': ['loadtest-edx-worker-v034']
            },
            'rollback_to_asgs': {
                'loadtest-edx-edxapp': ['loadtest-edx-edxapp-v097'],
                'loadtest-edx-worker': ['loadtest-edx-worker-v098']
            },
        }
        expected_output = {
            'ami_id': self.test_ami_id,
            'current_ami_id': self.test_ami_id,
            'current_asgs':
                {
                    'loadtest-edx-edxapp': ['loadtest-edx-edxapp-v099'],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v099']
                },
            'disabled_ami_id': self.test_ami_id,
            'disabled_asgs':
                {
                    'loadtest-edx-edxapp':
                        [
                            'loadtest-edx-edxapp-v058',
                            'loadtest-edx-edxapp-v059'
                        ],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v034'],
                },
        }

        # Rollback and check output.
        self.assertEqual(
            asgard.rollback(rollback_input['current_asgs'], rollback_input['rollback_to_asgs'], self.test_ami_id),
            expected_output
        )

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_rollback_with_failure_and_without_redeploy(self, req_mock):
        self._setup_rollback(req_mock)

        # The pending delete of the ASGs to rollback to causes the rollback to fail.
        self._mock_asgard_pending_delete(req_mock, self.rollback_to_asgs)

        rollback_input = {
            'current_asgs':
                {
                    'loadtest-edx-edxapp':
                        [
                            'loadtest-edx-edxapp-v058',
                            'loadtest-edx-edxapp-v059'
                        ],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v034']
                },
            'rollback_to_asgs':
                {
                    'loadtest-edx-edxapp': ['loadtest-edx-edxapp-v097'],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v098']
                },
        }
        expected_output = {
            'ami_id': None,
            'current_ami_id': None,
            'current_asgs':
                {
                    'loadtest-edx-edxapp':
                        [
                            'loadtest-edx-edxapp-v058',
                            'loadtest-edx-edxapp-v059'
                        ],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v034']
                },
            'disabled_ami_id': None,
            'disabled_asgs':
                {
                    'loadtest-edx-edxapp': ['loadtest-edx-edxapp-v097'],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v098']
                },
        }

        # Rollback and check output.
        # No AMI ID specified - so no deploy occurs after the rollback failure.
        self.assertEqual(
            asgard.rollback(rollback_input['current_asgs'], rollback_input['rollback_to_asgs']),
            expected_output
        )

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_rollback_with_failure_and_asgs_tagged_for_deletion(self, req_mock):
        self._setup_rollback(req_mock)

        tag_asg_for_deletion('loadtest-edx-edxapp-v097', -2000)
        tag_asg_for_deletion('loadtest-edx-worker-v098', -2000)
        self._mock_asgard_not_pending_delete(req_mock, self.rollback_to_asgs, json_builder=enabled_asg)

        rollback_input = {
            'current_asgs':
                {
                    'loadtest-edx-edxapp':
                        [
                            'loadtest-edx-edxapp-v058',
                            'loadtest-edx-edxapp-v059'
                        ],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v034']
                },
            'rollback_to_asgs':
                {
                    'loadtest-edx-edxapp': ['loadtest-edx-edxapp-v097'],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v098']
                },
        }
        # Deletion tags are removed from 97/98 and they're used for the rollback.
        expected_output = {
            'ami_id': self.test_ami_id,
            'current_ami_id': self.test_ami_id,
            'current_asgs':
                {
                    'loadtest-edx-edxapp': ['loadtest-edx-edxapp-v097'],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v098']
                },
            'disabled_ami_id': self.test_ami_id,
            'disabled_asgs':
                {
                    'loadtest-edx-edxapp':
                        [
                            'loadtest-edx-edxapp-v058',
                            'loadtest-edx-edxapp-v059'
                        ],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v034']
                },
        }

        # Rollback and check output.
        self.assertEqual(
            asgard.rollback(rollback_input['current_asgs'], rollback_input['rollback_to_asgs'], self.test_ami_id),
            expected_output
        )

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_rollback_asg_does_not_exist(self, req_mock):
        self._setup_rollback_deleted(req_mock)

        tag_asg_for_deletion('loadtest-edx-edxapp-v097', -2000)
        tag_asg_for_deletion('loadtest-edx-worker-v098', -2000)

        rollback_input = {
            'current_asgs':
                {
                    'loadtest-edx-edxapp':
                        [
                            'loadtest-edx-edxapp-v058',
                            'loadtest-edx-edxapp-v059'
                        ],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v034']
                },
            'rollback_to_asgs':
                {
                    'loadtest-edx-edxapp': ['loadtest-edx-edxapp-v097'],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v098']
                },
        }
        # Deletion tags are removed from 97/98 and they're used for the rollback.
        expected_output = {
            'ami_id': self.test_ami_id,
            'current_ami_id': self.test_ami_id,
            'current_asgs':
                {
                    'loadtest-edx-edxapp': ['loadtest-edx-edxapp-v099'],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v099']
                },
            'disabled_ami_id': self.test_ami_id,
            'disabled_asgs':
                {
                    'loadtest-edx-edxapp':
                        [
                            'loadtest-edx-edxapp-v058',
                            'loadtest-edx-edxapp-v059'
                        ],
                    'loadtest-edx-worker': ['loadtest-edx-worker-v034']
                },
        }

        # Rollback and check output.
        rollback_output = asgard.rollback(
            rollback_input['current_asgs'],
            rollback_input['rollback_to_asgs'],
            self.test_ami_id
        )

        self.assertEqual(
            rollback_output,
            expected_output
        )

    def test_is_asg_pending_delete(self, req_mock):
        asg = "loadtest-edx-edxapp-v060"
        self._mock_asgard_pending_delete(req_mock, [asg])
        self.assertTrue(asgard.is_asg_pending_delete(asg))

    def test_is_asg_not_pending_delete(self, req_mock):
        asg = "loadtest-edx-edxapp-v060"
        self._mock_asgard_not_pending_delete(req_mock, [asg])
        self.assertFalse(asgard.is_asg_pending_delete(asg))

    @data((disabled_asg, "loadtest-edx-edxapp-v060", False), (enabled_asg, "loadtest-edx-edxapp-v060", True))
    @unpack
    def test_is_asg_enabled(self, response_body, asg_name, expected_return, req_mock):
        url = asgard.ASG_INFO_URL.format(asg_name)
        req_mock.get(
            url,
            json=response_body(asg_name))
        self.assertEqual(asgard.is_asg_enabled(asg_name), expected_return)

    def test_is_asg_enabled_deleted_asg(self, req_mock):
        asg = "loadtest-edx-edxapp-v060"
        self._mock_asgard_not_pending_delete(req_mock, [asg], 404)
        self.assertEqual(asgard.is_asg_enabled(asg), False)

    def test_get_asg_info(self, req_mock):
        asg = "loadtest-edx-edxapp-v060"
        self._mock_asgard_not_pending_delete(req_mock, [asg])
        self.assertEqual(asgard.get_asg_info(asg), deleted_asg_not_in_progress(asg))

    def test_get_asg_info_html_response(self, req_mock):
        asg = "loadtest-edx-edxapp-v060"
        self._mock_asgard_not_pending_delete(req_mock, [asg], html_return=True)
        with self.assertRaises(BackendError):
            asgard.get_asg_info(asg)

    def test_get_asg_info_404(self, req_mock):
        asg = "loadtest-edx-edxapp-v060"
        self._mock_asgard_pending_delete(req_mock, [asg], 404)
        with self.assertRaises(ASGDoesNotExistException) as context_manager:
            asgard.get_asg_info(asg)
        error_message = "Autoscale group {} does not exist".format(asg)
        self.assertEqual(str(context_manager.exception), error_message)

    def test_get_asg_info_500(self, req_mock):
        asg = "loadtest-edx-edxapp-v060"
        self._mock_asgard_pending_delete(req_mock, [asg], 500)
        with self.assertRaises(BackendError) as context_manager:
            asgard.get_asg_info(asg)
        self.assertTrue(str(context_manager.exception).startswith("Asgard experienced an error:"))

    def test_get_asg_info_403(self, req_mock):
        asg = "loadtest-edx-edxapp-v060"
        self._mock_asgard_pending_delete(req_mock, [asg], 403)
        with self.assertRaises(BackendError) as context_manager:
            asgard.get_asg_info(asg)
        error_message = "Call to asgard failed with status code: {}".format(403)
        self.assertTrue(str(context_manager.exception).startswith(error_message))

    def test__iterate_and_delete_empty_asgs_empties(self, req_mock):
        """ Function should only delete if latest ASG is empty """
        asgs = [
            {
                'desiredCapacity': 8,
                'minSize': 2,
                'maxSize': 20,
                'autoScalingGroupName': 'loadtest-edx-edxapp-v1337'
            },
            {
                'desiredCapacity': 0,
                'minSize': 0,
                'maxSize': 0,
                'autoScalingGroupName': 'loadtest-edx-edxapp-v1338'
            },
            {
                'desiredCapacity': 0,
                'minSize': 0,
                'maxSize': 0,
                'autoScalingGroupName': 'loadtest-edx-edxapp-v1339'
            },
        ]

        assert len(asgs) == 3
        assert asgs[0]['autoScalingGroupName'] == 'loadtest-edx-edxapp-v1337'

        with mock.patch('tubular.asgard.delete_asg') as mock_delete_asg:
            asgard._iterate_and_delete_empty_asgs(asgs)
            mock_delete_asg.call_count == 2
            mock_delete_asg.call_args == ('loadtest-edx-edxapp-v1338', 'loadtest-edx-edxapp-v1339')

        assert len(asgs) == 1
        assert asgs[0]['autoScalingGroupName'] == 'loadtest-edx-edxapp-v1337'

    def test__iterate_and_delete_empty_asgs_one_full_asg_present(self, req_mock):
        """ Function should always leave 1 ASG remaining"""
        asgs = [
            {
                'desiredCapacity': 8,
                'minSize': 2,
                'maxSize': 20,
                'autoScalingGroupName': 'loadtest-edx-edxapp-v1337'
            },
        ]

        assert len(asgs) == 1
        assert asgs[0]['autoScalingGroupName'] == 'loadtest-edx-edxapp-v1337'

        with mock.patch('tubular.asgard.delete_asg') as mock_delete_asg:
            asgard._iterate_and_delete_empty_asgs(asgs)
            mock_delete_asg.assert_not_called()

        assert len(asgs) == 1
        assert asgs[0]['autoScalingGroupName'] == 'loadtest-edx-edxapp-v1337'

    def test__iterate_and_delete_empty_asgs_one_empty_asg_present(self, req_mock):
        """ Function should always leave 1 ASG remaining even if empty"""
        asgs = [
            {
                'desiredCapacity': 0,
                'minSize': 0,
                'maxSize': 0,
                'autoScalingGroupName': 'loadtest-edx-edxapp-v1337'
            },
        ]

        assert len(asgs) == 1
        assert asgs[0]['autoScalingGroupName'] == 'loadtest-edx-edxapp-v1337'

        with mock.patch('tubular.asgard.delete_asg') as mock_delete_asg:
            asgard._iterate_and_delete_empty_asgs(asgs)
            mock_delete_asg.assert_not_called()

        assert len(asgs) == 1
        assert asgs[0]['autoScalingGroupName'] == 'loadtest-edx-edxapp-v1337'

    def test__iterate_and_delete_empty_asgs_empty_in_the_middle(self, req_mock):
        """ Function should only delete if latest ASG is empty """
        asgs = [
            {
                'desiredCapacity': 8,
                'minSize': 2,
                'maxSize': 20,
                'autoScalingGroupName': 'loadtest-edx-edxapp-v1337'
            },
            {
                'desiredCapacity': 0,
                'minSize': 0,
                'maxSize': 0,
                'autoScalingGroupName': 'loadtest-edx-edxapp-v1338'
            },
            {
                'desiredCapacity': 8,
                'minSize': 2,
                'maxSize': 20,
                'autoScalingGroupName': 'loadtest-edx-edxapp-v1339'
            },
        ]

        assert len(asgs) == 3
        assert asgs[0]['autoScalingGroupName'] == 'loadtest-edx-edxapp-v1337'

        with mock.patch('tubular.asgard.delete_asg') as mock_delete_asg:
            asgard._iterate_and_delete_empty_asgs(asgs)
            mock_delete_asg.assert_not_called()

        assert len(asgs) == 3
        assert asgs[0]['autoScalingGroupName'] == 'loadtest-edx-edxapp-v1337'
        assert asgs[2]['autoScalingGroupName'] == 'loadtest-edx-edxapp-v1339'

    @data(
        (0, 0),
        (0, 2),
        (2, 0),
    )
    @unpack
    def test__asg_is_empty_true(self, desired_capacity, min_size, req_mock):
        """ Function should return True if condition met """
        asg = {
            'desiredCapacity': desired_capacity,
            'minSize': min_size,
        }
        assert asgard._asg_is_empty(asg) is True

    def test__asg_is_empty(self, req_mock):
        """ Function should return False if conditions are not met"""
        asg = {
            'desiredCapacity': 8,
            'minSize': 2,
        }
        assert asgard._asg_is_empty(asg) is False
