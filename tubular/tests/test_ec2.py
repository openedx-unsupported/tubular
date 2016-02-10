from collections import Iterable

import unittest

import boto
from boto.ec2.autoscale.launchconfig import LaunchConfiguration
from boto.ec2.autoscale.group import AutoScalingGroup
from boto.ec2.autoscale import Tag

from moto import mock_ec2, mock_autoscaling, mock_elb
from moto.ec2.utils import random_ami_id
from ..ec2 import *
from ..exception import ImageNotFoundException, MissingTagException
from ..utils import EDC

class TestEC2(unittest.TestCase):

    @mock_ec2
    def test_edc_for_ami(self):
        # Bad AMI Id
        self.assertRaises(ImageNotFoundException, edc_for_ami, "ami-fakeid")

        ec2 = boto.connect_ec2()
        reservation = ec2.run_instances(random_ami_id())
        instance_id = reservation.instances[0].id
        ami_id = ec2.create_image(instance_id, "Existing AMI")

        # AMI Exists but isn't tagged.
        self.assertRaises(MissingTagException, edc_for_ami, ami_id)

        ami = ec2.get_all_images(ami_id)[0]
        ami.add_tag("environment", "foo")
        ami.add_tag("deployment", "bar")
        ami.add_tag("cluster", "baz")

        actual_edc = edc_for_ami(ami_id)
        expected_edc = EDC("foo", "bar", "baz")

        # Happy Path
        self.assertEqual(expected_edc, actual_edc)

    @mock_autoscaling
    def test_asgs_for_edc(self):
        edc = EDC("foo","bar","baz")

        asgs = asgs_for_edc(edc)
        self.assertIsInstance(asgs, Iterable)

        asgs = list(asgs)
        num_asgs = len(asgs)
        self.assertEqual(num_asgs, 0, "Expected empty list of ASGs, got {}".format(num_asgs))

        self._create_asg_with_tags("untagged_asg", [])

        asgs = asgs_for_edc(edc)
        self.assertIsInstance(asgs, Iterable)

        asgs = list(asgs)
        num_asgs = len(asgs)
        self.assertEqual(num_asgs, 0, "Expected empty list of ASGs, got {}".format(num_asgs))

        self._create_asg_with_tags("partially_taggeg_asg", [
            Tag(key="environment", value="foo"),
            Tag(key="cluster", value="baz"),
            ])

        asgs = asgs_for_edc(edc)
        self.assertIsInstance(asgs, Iterable)

        asgs = list(asgs)
        num_asgs = len(asgs)
        self.assertEqual(num_asgs, 0, "Number of ASGs expected don't match actual.")

        self._create_asg_with_tags("tagged_asg", [
            Tag(key="environment", value="foo"),
            Tag(key="deployment", value="bar"),
            Tag(key="cluster", value="baz"),
            ])

        asgs = asgs_for_edc(edc)
        self.assertIsInstance(asgs, Iterable)

        asgs = list(asgs)
        num_asgs = len(asgs)
        self.assertEqual(num_asgs, 1, "Number of ASGs expected don't match actual.")

        self._create_asg_with_tags("tagged_asg2", [
            Tag(key="environment", value="foo"),
            Tag(key="deployment", value="bar"),
            Tag(key="cluster", value="baz"),
            ])

        asgs = asgs_for_edc(edc)
        self.assertIsInstance(asgs, Iterable)

        asgs = list(asgs)
        num_asgs = len(asgs)
        self.assertEqual(num_asgs, 2)

    def test_dict_from_tag_list(self):
        tag_list = []
        actual_dict = dict_from_tag_list(tag_list)
        expected_dict = {}
        self.assertEqual(expected_dict, actual_dict)

        tag_list = [
                Tag(key="some_key", value="some_value"),
                Tag(key="some_key2", value="some_value2"),
                ]

        expected_dict = {
            "some_key": "some_value",
            "some_key2": "some_value2"
            }
        actual_dict = dict_from_tag_list(tag_list)
        self.assertEqual(expected_dict, actual_dict)

        tag_list = [
                Tag(key="some_key", value="some_value"),
                Tag(key="some_key", value="some_value2"),
                ]

        expected_dict = {
            "some_key": "some_value2",
            }
        actual_dict = dict_from_tag_list(tag_list)
        self.assertEqual(expected_dict, actual_dict)

    def _create_asg_with_tags(self, asg_name, tags):
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
            tags=tags,
        )
        conn.create_auto_scaling_group(group)
