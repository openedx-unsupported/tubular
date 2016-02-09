import boto
import unittest
from moto import mock_ec2
from moto.ec2.utils import random_ami_id
from ..ec2 import edc_for_ami
from ..exception import ImageNotFoundException, MissingTagException
from ..utils import EDC

class TestEdcForAmi(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock_ec2
    def test_edc_for_ami(self):
        self.assertRaises(ImageNotFoundException, edc_for_ami, "ami-fakeid")

        ec2 = boto.connect_ec2()
        reservation = ec2.run_instances(random_ami_id())
        instance_id = reservation.instances[0].id
        ami_id = ec2.create_image(instance_id, "Existing AMI")

        self.assertRaises(MissingTagException, edc_for_ami, ami_id)

        ami = ec2.get_all_images(ami_id)[0]
        ami.add_tag("environment", "foo")
        ami.add_tag("deployment", "bar")
        ami.add_tag("cluster", "baz")

        actual_edc = edc_for_ami(ami_id)

        expected_edc = EDC("foo", "bar", "baz")
        self.assertEqual(expected_edc, actual_edc)
