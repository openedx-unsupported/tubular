from collections import Iterable

import boto
import mock
import unittest

from boto.ec2.autoscale.launchconfig import LaunchConfiguration
from boto.ec2.autoscale.group import AutoScalingGroup
from boto.ec2.autoscale import Tag

from ddt import ddt, data, file_data, unpack
from moto import mock_ec2, mock_autoscaling, mock_elb
from moto.ec2.utils import random_ami_id
from ..ec2 import *
from ..exception import *
from ..utils import EDC

@ddt
class TestEC2(unittest.TestCase):
    _multiprocess_can_split_ = True

    @mock_ec2
    def test_edc_for_ami_bad_id(self):
        # Bad AMI Id
        self.assertRaises(ImageNotFoundException, edc_for_ami, "ami-fakeid")

    @mock_ec2
    def test_edc_for_untagged_ami(self):
        ec2 = boto.connect_ec2()
        reservation = ec2.run_instances(random_ami_id())
        instance_id = reservation.instances[0].id
        ami_id = ec2.create_image(instance_id, "Existing AMI")

        # AMI Exists but isn't tagged.
        self.assertRaises(MissingTagException, edc_for_ami, ami_id)

    @mock_ec2
    def test_edc2_for_tagged_ami(self):
        ec2 = boto.connect_ec2()
        reservation = ec2.run_instances(random_ami_id())
        instance_id = reservation.instances[0].id
        ami_id = ec2.create_image(instance_id, "Existing AMI")
        ami = ec2.get_all_images(ami_id)[0]
        ami.add_tag("environment", "foo")
        ami.add_tag("deployment", "bar")
        ami.add_tag("cluster", "baz")

        actual_edc = edc_for_ami(ami_id)
        expected_edc = EDC("foo", "bar", "baz")

        # Happy Path
        self.assertEqual(expected_edc, actual_edc)

    @mock_autoscaling
    @file_data("test_asgs_for_edc_data.json")
    def test_asgs_for_edc(self, params):
        asgs, expected_returned = params

        edc = EDC("foo","bar","baz")

        for name, tags in asgs.iteritems():
            self._create_asg_with_tags(name, tags)

        asgs = asgs_for_edc(edc)
        self.assertIsInstance(asgs, Iterable)

        asgs = list(asgs)
        num_asgs = len(asgs)
        self.assertEquals(num_asgs, expected_returned)

    def _create_asg_with_tags(self, asg_name, tags):
        tag_list = [ Tag(key=k, value=v) for k,v in tags.iteritems() ]

        # Create asgs
        elb_conn = boto.ec2.elb.connect_to_region('us-east-1')

        conn = boto.ec2.autoscale.connect_to_region('us-east-1')
        config = LaunchConfiguration(
            name='{}_lc'.format(asg_name),
            image_id='ami-abcd1234',
            instance_type='t2.medium',
        )
        conn.create_launch_configuration(config)

        group = AutoScalingGroup(
            name=asg_name,
            availability_zones=['us-east-1c', 'us-east-1b'],
            default_cooldown=60,
            desired_capacity=2,
            health_check_period=100,
            health_check_type="EC2",
            max_size=2,
            min_size=2,
            launch_config=config,
            placement_group="test_placement",
            vpc_zone_identifier='subnet-1234abcd',
            termination_policies=["OldestInstance", "NewestInstance"],
            tags=tag_list,
        )
        conn.create_auto_scaling_group(group)

    @mock_autoscaling
    @mock_ec2
    def test_wait_for_in_service(self):
        self._create_asg_with_tags("healthy_asg", {"foo": "bar"})
        self.assertEqual(None, wait_for_in_service(["healthy_asg"], 2))

    @mock_autoscaling
    @mock_ec2
    def test_wait_for_in_service_lifecycle_failure(self):
        asg_name = "unhealthy_asg"
        self._create_asg_with_tags(asg_name, {"foo": "bar"})
        autoscale = boto.connect_autoscale()
        asgs = autoscale.get_all_groups([asg_name])
        asg = asgs[0]
        asg.instances[0].lifecycle_state = "NotInService"
        with mock.patch("boto.ec2.autoscale.AutoScaleConnection.get_all_groups", return_value=asgs) as mock_connection:
            self.assertRaises(TimeoutException, wait_for_in_service,[asg_name], 2)


    @mock_autoscaling
    @mock_ec2
    def test_wait_for_in_service_health_failure(self):
        asg_name = "unhealthy_asg"
        self._create_asg_with_tags(asg_name, {"foo": "bar"})
        autoscale = boto.connect_autoscale()
        asgs = autoscale.get_all_groups([asg_name])
        asg = asgs[0]
        asg.instances[0].health_status = "Unhealthy"
        with mock.patch("boto.ec2.autoscale.AutoScaleConnection.get_all_groups", return_value=asgs) as mock_connection:
            self.assertRaises(TimeoutException, wait_for_in_service,[asg_name], 2)

