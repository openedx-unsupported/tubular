"""
Tests of the Command-line script for boto add ingress.
"""

import unittest

import boto3
import click
import mock
import six
from boto3.exceptions import Boto3Error
from click.testing import CliRunner
from moto import mock_autoscaling, mock_ec2, mock_elb
from moto.ec2.utils import random_ami_id

import tubular.ec2 as ec2
from tubular.admin.boto_to_add_ingress import add_ingress_rule
from tubular.tests.test_utils import *
from tubular.utils import EDP


class TestAsgard(unittest.TestCase):
    """
    Class containing all Asgard tests.
    """

    @mock_ec2
    def _make_fake_ami(self, environment='foo', deployment='bar', play='baz'):
        """
        Method to make a fake AMI.
        """
        ec2_client = boto3.client('ec2')
        response = ec2_client.run_instances(ImageId=random_ami_id(), MinCount=1, MaxCount=1)
        instance_id = response['Instances'][0]['InstanceId']
        ami_name = 'fake-ami-for-testing'
        ami_description = 'This is a fake AMI created for testing purposes'
        response = ec2_client.create_image(
            InstanceId=instance_id, Name=ami_name,
            Description=ami_description, NoReboot=True,
        )
        ami_id = response['ImageId']
        ec2_client.create_tags(
            Resources=[ami_id], Tags=[
                {'Key': 'environment', 'Value': environment},
                {'Key': 'deployment', 'Value': deployment},
                {'Key': 'play', 'Value': play}
            ]
        )

        return ami_id

    @mock_ec2
    @mock_autoscaling
    @mock_elb
    def test_ingress_script(self):
        fake_ami_id = self._make_fake_ami()
        fake_elb_name = "healthy-lb-1"
        fake_elb = create_elb(fake_elb_name)
        fake_asg_name = "fully_tagged_asg"
        fake_asg_tags = {
            "environment": "foo",
            "deployment": "bar",
            "play": "baz"
        }

        create_asg_with_tags(
            fake_asg_name,
            fake_asg_tags,
            ami_id=fake_ami_id,
            elbs=[fake_elb]
        )

        runner = CliRunner()
        with mock.patch('tubular.admin.boto_to_add_ingress.six.moves.input') as mocked_input:
            mocked_input.return_value='yes'

            result = runner.invoke(
                add_ingress_rule , [
                    '--go-agent-security-group', 'deployment-grp',
                    '--go-agent-security-group-owner', 'deployment-grp for testing'
                ],
            )

            assert result.exit_code == 0
            assert result.output == ''
