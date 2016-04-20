from collections import Iterable

import mock
import unittest

from ddt import ddt, data, file_data, unpack
from moto import mock_ec2, mock_autoscaling, mock_elb
from moto.ec2.utils import random_ami_id
from .test_utils import create_asg_with_tags, create_elb, clone_elb_instances_with_state
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
        ami.add_tag("play", "baz")

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
            create_asg_with_tags(name, tags)

        asgs = asgs_for_edc(edc)
        self.assertIsInstance(asgs, Iterable)

        asgs = list(asgs)
        num_asgs = len(asgs)
        self.assertEquals(num_asgs, expected_returned)

    @mock_autoscaling
    @mock_ec2
    def test_wait_for_in_service(self):
        create_asg_with_tags("healthy_asg", {"foo": "bar"})
        self.assertEqual(None, wait_for_in_service(["healthy_asg"], 2))

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
            self.assertRaises(TimeoutException, wait_for_in_service,[asg_name], 2)


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
            self.assertRaises(TimeoutException, wait_for_in_service,[asg_name], 2)


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
            self.assertEqual(None, wait_for_healthy_elbs([first_elb_name, second_elb_name], 3))

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
            self.assertRaises(TimeoutException, wait_for_healthy_elbs, [elb_name], 2)
