from collections import Iterable

import mock
import unittest
import boto
import datetime

from ddt import ddt, data, file_data, unpack
from moto import mock_ec2, mock_autoscaling, mock_elb
from moto.ec2.utils import random_ami_id
from .test_utils import create_asg_with_tags, create_elb, clone_elb_instances_with_state
from .. import ec2
from ..exception import *
from ..utils import EDP


@ddt
class TestEC2(unittest.TestCase):
    _multiprocess_can_split_ = True

    @mock_ec2
    def test_edp_for_ami_bad_id(self):
        # Bad AMI Id
        self.assertRaises(ImageNotFoundException, ec2.edp_for_ami, "ami-fakeid")

    @mock_ec2
    def test_edp_for_untagged_ami(self):
        ec2_connection = boto.connect_ec2()
        reservation = ec2_connection.run_instances(random_ami_id())
        instance_id = reservation.instances[0].id
        ami_id = ec2_connection.create_image(instance_id, "Existing AMI")

        # AMI Exists but isn't tagged.
        self.assertRaises(MissingTagException, ec2.edp_for_ami, ami_id)

    @mock_ec2
    def test_edp2_for_tagged_ami(self):
        ec2_connection = boto.connect_ec2()
        reservation = ec2_connection.run_instances(random_ami_id())
        instance_id = reservation.instances[0].id
        ami_id = ec2_connection.create_image(instance_id, "Existing AMI")
        ami = ec2_connection.get_all_images(ami_id)[0]
        ami.add_tag("environment", "foo")
        ami.add_tag("deployment", "bar")
        ami.add_tag("play", "baz")

        actual_edp = ec2.edp_for_ami(ami_id)
        expected_edp = EDP("foo", "bar", "baz")

        # Happy Path
        self.assertEqual(expected_edp, actual_edp)

    @mock_autoscaling
    @file_data("test_asgs_for_edp_data.json")
    def test_asgs_for_edp(self, params):
        asgs, expected_returned = params

        edp = EDP("foo","bar","baz")

        for name, tags in asgs.iteritems():
            create_asg_with_tags(name, tags)

        asgs = ec2.asgs_for_edp(edp)
        self.assertIsInstance(asgs, Iterable)

        asgs = list(asgs)
        num_asgs = len(asgs)
        self.assertEquals(num_asgs, expected_returned)

    @mock_autoscaling
    @mock_ec2
    def test_wait_for_in_service(self):
        create_asg_with_tags("healthy_asg", {"foo": "bar"})
        self.assertEqual(None, ec2.wait_for_in_service(["healthy_asg"], 2))

    @mock_autoscaling
    @mock_ec2
    def test_wait_for_in_service_lifecycle_failure(self):
        asg_name = "unhealthy_asg"
        create_asg_with_tags(asg_name, {"foo": "bar"})
        autoscale = boto.connect_autoscale()
        asgs = autoscale.get_all_groups([asg_name])
        asg = asgs[0]
        asg.instances[0].lifecycle_state = "NotInService"
        with mock.patch("boto.ec2.autoscale.AutoScaleConnection.get_all_groups", return_value=asgs) as mock_connection:
            self.assertRaises(TimeoutException, ec2.wait_for_in_service,[asg_name], 2)

    @mock_autoscaling
    @mock_ec2
    def test_wait_for_in_service_health_failure(self):
        asg_name = "unhealthy_asg"
        create_asg_with_tags(asg_name, {"foo": "bar"})
        autoscale = boto.connect_autoscale()
        asgs = autoscale.get_all_groups([asg_name])
        asg = asgs[0]
        asg.instances[0].health_status = "Unhealthy"
        with mock.patch("boto.ec2.autoscale.AutoScaleConnection.get_all_groups", return_value=asgs) as mock_connection:
            self.assertRaises(TimeoutException, ec2.wait_for_in_service,[asg_name], 2)

    @mock_elb
    @mock_ec2
    def test_wait_for_healthy_elbs(self):
        first_elb_name = "healthy-lb-1"
        second_elb_name = "healthy-lb-2"
        first_elb = create_elb(first_elb_name)
        second_elb = create_elb(second_elb_name)
        mock_function = "boto.ec2.elb.loadbalancer.LoadBalancer.get_instance_health"

        # Setup a side effect to simulate how a instances may come online in the load balancer.
        # 2 load balancers * 2 instances per * 3 iterations (They way these instances come online in to the load
        # balancer will ensure that the ELB will be removed from the list on the second iteration, then the second ELB
        # is removed on the 3rd iteation.
        first_elb_instances = first_elb.get_instance_health()
        second_elb_instances = second_elb.get_instance_health()

        return_vals = [
                clone_elb_instances_with_state(first_elb_instances, "OutOfService"),
                clone_elb_instances_with_state(second_elb_instances, "OutOfService")
        ]
        return_vals += [
            clone_elb_instances_with_state(first_elb_instances, "InService"),
            clone_elb_instances_with_state(second_elb_instances, "OutOfService")
        ]
        return_vals += [clone_elb_instances_with_state(second_elb_instances, "InService")]

        with mock.patch(mock_function, side_effect=return_vals) as mock_call:
            self.assertEqual(None, ec2.wait_for_healthy_elbs([first_elb_name, second_elb_name], 3))

    @mock_elb
    @mock_ec2
    def test_wait_for_healthy_elbs_failure(self):
        elb_name = "unhealthy-lb"
        lb = create_elb(elb_name)
        # Make one of the instances un-healthy.
        instances = lb.get_instance_health()
        instances[0].state = "OutOfService"
        mock_function = "boto.ec2.elb.loadbalancer.LoadBalancer.get_instance_health"
        with mock.patch(mock_function, return_value=instances) as mock_call:
            self.assertRaises(TimeoutException, ec2.wait_for_healthy_elbs, [elb_name], 2)

    # TODO: Currently motto does not support the method create_or_update_tags. When support is added this test should
    # be updated to test the functioanlity of tag_asg_for_deletion
    # @mock_autoscaling
    # @mock_elb
    # @mock_ec2
    # def test_create_or_update_tags_on_asg(self):
    #     asg_name = "test-asg-random-tags"
    #     tag_name = "some-tag-name"
    #     tag_value = "some tag value"
    #     tag = Tag(key=tag_name,
    #               value=tag_value,
    #               propagate_at_launch=False,
    #               resource_id=asg_name)
    #
    #     autoscale = boto.connect_autoscale()
    #     lc = boto.ec2.autoscale.LaunchConfiguration(name='my-launch_config', image_id='my-ami',
    #                              key_name='my_key_name',
    #                              security_groups=['my_security_groups'])
    #     autoscale.create_launch_configuration(lc)
    #     asg = boto.ec2.autoscale.AutoScalingGroup(group_name=asg_name, load_balancers=['my-lb'],
    #                           availability_zones=['us-east-1a', 'us-east-1b'],
    #                           launch_config=lc, min_size=4, max_size=8,
    #                           connection=autoscale)
    #     create_elb('my-lb')
    #     autoscale.create_auto_scaling_group(asg)
    #
    #     tag_asg_for_deletion(asg_name, [tag])
    #
    #     the_asg = autoscale.get_all_groups(asg_name)
    #     self.assertTrue(len([tag for tag in the_asg.tags if tag.key==tag_name and tag.value==tag_value]) == 1)
    #     # more asserts here

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_get_asgs_pending_delete(self):
        asg_name = "test-asg-deletion"
        deletion_dttm_str = datetime.datetime.utcnow().isoformat()
        create_asg_with_tags(asg_name, {ec2.ASG_DELETE_TAG_KEY:deletion_dttm_str})

        asgs = ec2.get_asgs_pending_delete()
        self.assertTrue(len(asgs) == 1)
        asg = asgs.pop()
        self.assertEqual(asg.name, asg_name)
        self.assertEqual(asg.tags[0].key, ec2.ASG_DELETE_TAG_KEY)
        self.assertEqual(asg.tags[0].value, deletion_dttm_str)

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_get_asgs_pending_delete_incorrectly_formatted_timestamp(self):
        asg_name1 = "test-asg-deletion"
        asg_name2 = "test-asg-deletion-bad-timestamp"
        deletion_dttm_str1 = datetime.datetime.utcnow().isoformat()
        deletion_dttm_str2 = "2016-05-18 18:19:46.144884"
        group1 = create_asg_with_tags(asg_name1, {ec2.ASG_DELETE_TAG_KEY: deletion_dttm_str1})
        group2 = create_asg_with_tags(asg_name2, {ec2.ASG_DELETE_TAG_KEY: deletion_dttm_str2})

        asgs = ec2.get_asgs_pending_delete()
        self.assertTrue(len(asgs) == 1)
        # boto.ec2.autoscale.group.AutoScalingGroup does not implement __eq__ so we need to iterate the list to see if
        # the ASGs we are interested in are members
        self.assertTrue(len([asg for asg in asgs if asg.name == asg_name1]) == 1)
        self.assertTrue(len([asg for asg in asgs if asg.name == asg_name2]) == 0)

    def test_create_tag_for_asg_deletion(self):
        asg_name = "test-asg-tags"
        tag = ec2.create_tag_for_asg_deletion(asg_name)

        self.assertEqual(tag.key, ec2.ASG_DELETE_TAG_KEY)
        self.assertEqual(tag.resource_id, asg_name)
        self.assertFalse(tag.propagate_at_launch)
        datetime.datetime.strptime(tag.value, ec2.ISO_DATE_FORMAT)

    def test_create_tag_for_asg_deletion_delta_correct(self):
        # Python built-in types are immutable so we can't use @mock.patch
        class NewDateTime(datetime.datetime):
            @classmethod
            def utcnow(cls):
                return cls(2016, 5, 18, 01, 00, 00, 000000)
        built_in_datetime = ec2.datetime

        # The instance of datetime becomes local to the module it's import in to. We must patch datetime using the
        # module instance that is imported in to the ec2 module.
        ec2.datetime = NewDateTime

        asg_name = "test-asg-tags"
        tag = ec2.create_tag_for_asg_deletion(asg_name, 10)
        self.assertEqual(tag.value, datetime.datetime(2016, 5, 18, 01, 00, 10, 000000).isoformat())
        tag = ec2.create_tag_for_asg_deletion(asg_name, 300)
        self.assertEqual(tag.value, datetime.datetime(2016, 5, 18, 01, 05, 00, 000000).isoformat())

        # Undo the monkey patch
        ec2.datetime = built_in_datetime
