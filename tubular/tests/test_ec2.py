"""
Tests of the code interacting with the boto EC2 API.
"""

import datetime
import unittest

import boto
import ddt
import mock
import six
from boto.exception import BotoServerError
from moto import mock_ec2, mock_autoscaling, mock_elb
from moto.ec2.utils import random_ami_id

import tubular.ec2 as ec2
from tubular.exception import (
    ImageNotFoundException,
    TimeoutException,
    MissingTagException,
    MultipleImagesFoundException
)
from tubular.tests.test_utils import create_asg_with_tags, create_elb, clone_elb_instances_with_state
from tubular.utils import EDP


@ddt.ddt
class TestEC2(unittest.TestCase):
    """
    Class containing tests of code interacting with EC2.
    """
    _multiprocess_can_split_ = True

    def _make_fake_ami(self, environment='foo', deployment='bar', play='baz'):
        """
        Method to make a fake AMI.
        """
        ec2_connection = boto.connect_ec2()
        reservation = ec2_connection.run_instances(random_ami_id())
        instance_id = reservation.instances[0].id
        ami_id = ec2_connection.create_image(instance_id, "Existing AMI")
        ami = ec2_connection.get_all_images(ami_id)[0]
        ami.add_tag("environment", environment)
        ami.add_tag("deployment", deployment)
        ami.add_tag("play", play)
        return ami_id

    @mock_ec2
    def test_ami_edp_validate_for_bad_id(self):
        # Bad AMI Id
        self.assertRaises(
            ImageNotFoundException,
            ec2.validate_edp,
            'ami-fakeid',
            'fake_e',
            'fake_d',
            'fake_p'
        )

    @ddt.data(
        (True, ("foo", "bar", "baz")),
        (False, ("---", "bar", "baz")),
        (False, ("foo", "---", "baz")),
        (False, ("foo", "bar", "---")),
        (False, ("---", "---", "baz")),
        (False, ("---", "bar", "---")),
        (False, ("foo", "---", "---")),
        (False, ("---", "---", "---")),
        (False, ("baz", "bar", "foo")),
    )
    @ddt.unpack
    @mock_ec2
    def test_ami_edp_validate_ami_id(self, expected_ret, edp):
        fake_ami_id = self._make_fake_ami()
        self.assertEqual(ec2.validate_edp(fake_ami_id, *edp), expected_ret)

    @mock_ec2
    def test_restrict_ami_to_stage(self):
        self.assertEqual(True, ec2.is_stage_ami(self._make_fake_ami(environment='stage')))
        self.assertEqual(False, ec2.is_stage_ami(self._make_fake_ami(environment='prod')))
        self.assertEqual(False, ec2.is_stage_ami(self._make_fake_ami(deployment='stage', play='stage')))

    @mock_elb
    @mock_ec2
    @mock_autoscaling
    def test_ami_for_edp_missing_edp(self):
        # Non-existent EDP
        with self.assertRaises(ImageNotFoundException):
            ec2.active_ami_for_edp('One', 'Two', 'Three')

    @mock_autoscaling
    @mock_elb
    @mock_ec2
    def test_ami_for_edp_success(self):
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
        self.assertEqual(ec2.active_ami_for_edp('foo', 'bar', 'baz'), fake_ami_id)

    @unittest.skip("Test always fails due to not successfuly creating two different AMI IDs in single ELB.")
    @mock_autoscaling
    @mock_elb
    @mock_ec2
    def test_ami_for_edp_multiple_amis(self):
        fake_ami_id1 = self._make_fake_ami()
        fake_ami_id2 = self._make_fake_ami()
        fake_elb_name = "healthy-lb-1"
        fake_elb = create_elb(fake_elb_name)
        fake_asg_name1 = "fully_tagged_asg1"
        fake_asg_name2 = "fully_tagged_asg2"
        fake_asg_tags = {
            "environment": "foo",
            "deployment": "bar",
            "play": "baz"
        }
        create_asg_with_tags(
            fake_asg_name1,
            fake_asg_tags,
            ami_id=fake_ami_id1,
            elbs=[fake_elb]
        )
        create_asg_with_tags(
            fake_asg_name2,
            fake_asg_tags,
            ami_id=fake_ami_id2,
            elbs=[fake_elb]
        )
        with self.assertRaises(MultipleImagesFoundException):
            ec2.active_ami_for_edp('foo', 'bar', 'baz')

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
        actual_edp = ec2.edp_for_ami(self._make_fake_ami())
        expected_edp = EDP("foo", "bar", "baz")

        # Happy Path
        self.assertEqual(expected_edp, actual_edp)

    @mock_autoscaling
    @mock_ec2
    @ddt.file_data("test_asgs_for_edp_data.json")
    def test_asgs_for_edp(self, params):
        asgs, expected_returned_count, expected_asg_names_list = params

        edp = EDP("foo", "bar", "baz")

        for name, tags in six.viewitems(asgs):
            create_asg_with_tags(name, tags)

        asgs = ec2.asgs_for_edp(edp)
        self.assertIsInstance(asgs, list)

        self.assertEqual(len(asgs), expected_returned_count)
        self.assertTrue(all(asg_name in asgs for asg_name in expected_asg_names_list))

    @ddt.data(
        (103, 103, None),
        (103, 103, []),
        (103, 1, ["asg_1"]),
        (103, 3, ["asg_1", "asg_11", "asg_100"])

    )
    @ddt.unpack
    @mock_autoscaling
    @mock_ec2
    def test_get_all_autoscale_groups(self, asg_count, expected_result_count, name_filter):
        """
        While I have attempted to test for pagination the moto library does not seem to support this and returns
        all of the ASGs created on the first get request and not 50 per request.
        """
        for i in range(asg_count):
            create_asg_with_tags("asg_{}".format(i), {"environment": "foo", "deployment": "bar", "play": "baz"})
        asgs = ec2.get_all_autoscale_groups(name_filter)

        self.assertIsInstance(asgs, list)
        self.assertEqual(len(asgs), expected_result_count)
        if name_filter:
            self.assertTrue(all(asg.name in name_filter for asg in asgs))

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
        with mock.patch("boto.ec2.autoscale.AutoScaleConnection.get_all_groups", return_value=asgs):
            self.assertRaises(TimeoutException, ec2.wait_for_in_service, [asg_name], 2)

    @mock_autoscaling
    @mock_ec2
    def test_wait_for_in_service_health_failure(self):
        asg_name = "unhealthy_asg"
        create_asg_with_tags(asg_name, {"foo": "bar"})
        autoscale = boto.connect_autoscale()
        asgs = autoscale.get_all_groups([asg_name])
        asg = asgs[0]
        asg.instances[0].health_status = "Unhealthy"
        with mock.patch("boto.ec2.autoscale.AutoScaleConnection.get_all_groups", return_value=asgs):
            self.assertRaises(TimeoutException, ec2.wait_for_in_service, [asg_name], 2)

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

        with mock.patch(mock_function, side_effect=return_vals):
            with mock.patch('tubular.ec2.WAIT_SLEEP_TIME', 1):
                self.assertEqual(None, ec2.wait_for_healthy_elbs([first_elb_name, second_elb_name], 3))

    @mock_elb
    @mock_ec2
    def test_wait_for_healthy_elbs_failure(self):
        elb_name = "unhealthy-lb"
        load_balancer = create_elb(elb_name)
        # Make one of the instances un-healthy.
        instances = load_balancer.get_instance_health()
        instances[0].state = "OutOfService"
        mock_function = "boto.ec2.elb.loadbalancer.LoadBalancer.get_instance_health"
        with mock.patch(mock_function, return_value=instances):
            self.assertRaises(TimeoutException, ec2.wait_for_healthy_elbs, [elb_name], 2)

    @mock_autoscaling
    @mock_elb
    @mock_ec2
    def _setup_test_asg_to_be_deleted(self):
        """
        Setup a test ASG that is tagged to be deleted.
        """
        # pylint: disable=attribute-defined-outside-init
        self.test_asg_name = "test-asg-random-tags"
        self.test_autoscale = boto.connect_autoscale()
        launch_config = boto.ec2.autoscale.LaunchConfiguration(
            name='my-launch_config',
            image_id='my-ami',
            key_name='my_key_name',
            security_groups=['my_security_groups']
        )
        self.test_autoscale.create_launch_configuration(launch_config)
        asg = boto.ec2.autoscale.AutoScalingGroup(
            group_name=self.test_asg_name,
            load_balancers=['my-lb'],
            availability_zones=['us-east-1a', 'us-east-1b'],
            launch_config=launch_config,
            min_size=4,
            max_size=8,
            connection=self.test_autoscale
        )
        create_elb('my-lb')
        self.test_autoscale.create_auto_scaling_group(asg)
        ec2.tag_asg_for_deletion(self.test_asg_name, 0)
        self.test_asg = self.test_autoscale.get_all_groups([self.test_asg_name])[0]

    @mock_autoscaling
    @mock_elb
    @mock_ec2
    def test_create_or_update_tags_on_asg(self):
        self._setup_test_asg_to_be_deleted()

        # Ensure a single delete tag exists.
        delete_tags = [tag for tag in self.test_asg.tags if tag.key == ec2.ASG_DELETE_TAG_KEY]
        self.assertEqual(len(delete_tags), 1)

        # Ensure tag value is a parseable datetime.
        delete_tag = delete_tags.pop()
        self.assertIsInstance(delete_tag.value, six.string_types)
        datetime.datetime.strptime(delete_tag.value, ec2.ISO_DATE_FORMAT)

    # Moto does not currently implement delete_tags() - so this test can't complete successfully.
    # Once moto implements delete_tags(), uncomment this test.
    # @mock_autoscaling
    # @mock_elb
    # @mock_ec2
    # def test_delete_tags_on_asg(self):
    #     self._setup_test_asg_to_be_deleted()

    #     # Remove the delete tag from the ASG.
    #     ec2.remove_asg_deletion_tag(self.test_asg_name)

    #     # Re-fetch the ASG.
    #     self.test_asg = self.test_autoscale.get_all_groups([self.test_asg_name])[0]

    #     # Ensure no delete tag exists.
    #     delete_tags = [tag for tag in the_asg.tags if tag.key == ec2.ASG_DELETE_TAG_KEY]
    #     self.assertTrue(len(delete_tags) == 0)

    @mock_autoscaling
    @mock_ec2
    @mock_elb
    def test_get_asgs_pending_delete(self):
        asg_name = "test-asg-deletion"
        deletion_dttm_str = datetime.datetime.utcnow().isoformat()
        create_asg_with_tags(asg_name, {ec2.ASG_DELETE_TAG_KEY: deletion_dttm_str})

        asgs = ec2.get_asgs_pending_delete()
        self.assertEqual(len(asgs), 1)
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
        create_asg_with_tags(asg_name1, {ec2.ASG_DELETE_TAG_KEY: deletion_dttm_str1})
        create_asg_with_tags(asg_name2, {ec2.ASG_DELETE_TAG_KEY: deletion_dttm_str2})

        asgs = ec2.get_asgs_pending_delete()
        self.assertEqual(len(asgs), 1)
        # boto.ec2.autoscale.group.AutoScalingGroup does not implement __eq__ so we need to iterate the list to see if
        # the ASGs we are interested in are members
        self.assertEqual(len([asg for asg in asgs if asg.name == asg_name1]), 1)
        self.assertEqual(len([asg for asg in asgs if asg.name == asg_name2]), 0)

    def test_create_tag_for_asg_deletion(self):
        asg_name = "test-asg-tags"
        tag = ec2.create_tag_for_asg_deletion(asg_name, 1)

        self.assertEqual(tag.key, ec2.ASG_DELETE_TAG_KEY)
        self.assertEqual(tag.resource_id, asg_name)
        self.assertFalse(tag.propagate_at_launch)
        datetime.datetime.strptime(tag.value, ec2.ISO_DATE_FORMAT)

    def test_create_tag_for_asg_deletion_delta_correct(self):
        # Python built-in types are immutable so we can't use @mock.patch
        class NewDateTime(datetime.datetime):
            """
            Stub class for mocking datetime.
            """

            @classmethod
            def utcnow(cls):
                """
                Stub method returning a UTC datetime.
                """
                return cls(2016, 5, 18, 1, 0, 0, 0)

        built_in_datetime = ec2.datetime

        # The instance of datetime becomes local to the module it's import in to. We must patch datetime using the
        # module instance that is imported in to the ec2 module.
        ec2.datetime = NewDateTime

        asg_name = "test-asg-tags"
        tag = ec2.create_tag_for_asg_deletion(asg_name, 10)
        self.assertEqual(tag.value, datetime.datetime(2016, 5, 18, 1, 0, 10, 0).isoformat())
        tag = ec2.create_tag_for_asg_deletion(asg_name, 300)
        self.assertEqual(tag.value, datetime.datetime(2016, 5, 18, 1, 5, 0, 0).isoformat())

        # Undo the monkey patch
        ec2.datetime = built_in_datetime

    @ddt.data(
        (103, 103, None),
        (103, 103, []),
        (103, 1, ["elb_1"]),
        (103, 3, ["elb_1", "elb_11", "elb_100"])

    )
    @ddt.unpack
    @mock_elb
    def test_get_all_load_balancers(self, elb_count, expected_result_count, name_filter):
        """
        While I have attempted to test for pagination the moto library does not seem to support this and returns
        all of the ELBs created on the first get request and not 50 per request.
        """
        for i in range(elb_count):
            create_elb("elb_{}".format(i))
        elb = ec2.get_all_load_balancers(name_filter)

        self.assertIsInstance(elb, list)
        self.assertEqual(len(elb), expected_result_count)
        if name_filter:
            self.assertTrue(all(asg.name in name_filter for asg in elb))

    @ddt.data(
        (400,
         ('<ErrorResponse xmlns="http://autoscaling.amazonaws.com/doc/2011-01-01/">'
          '  <Error>'
          '     <Type>Sender</Type>'
          '     <Code>Throttling</Code>'
          '     <Message>Rate exceeded</Message>'
          '  </Error>'
          '  <RequestId>8xb4df00d</RequestId>'
          '</ErrorResponse>'),
         False),
        ("400",
         ('<ErrorResponse xmlns="http://autoscaling.amazonaws.com/doc/2011-01-01/">'
          '  <Error>'
          '     <Type>Sender</Type>'
          '     <Code>Throttling</Code>'
          '     <Message>Rate exceeded</Message>'
          '  </Error>'
          '  <RequestId>8xb4df00d</RequestId>'
          '</ErrorResponse>'),
         False),
        ('junk', '<ErrorResponse xmlns="http://autoscaling.amazonaws.com/doc/2011-01-01/"></ErrorResponse>', True),
        (200, '<ErrorResponse xmlns="http://autoscaling.amazonaws.com/doc/2011-01-01/"></ErrorResponse>', True),
        (400, '<ErrorResponse xmlns="http://autoscaling.amazonaws.com/doc/2011-01-01/"></ErrorResponse>', True),
        (400, 'BotoServerError requires real XML here, this should evaluate to None', True)
    )
    @ddt.unpack
    def test_giveup_if_not_throttling(self, status, body, expected_result):
        ex = BotoServerError(status, "reasons", body)
        self.assertEqual(ec2.giveup_if_not_throttling(ex), expected_result)

    @ddt.data(
        (
                [
                    {
                        'ami_id': 'ami-1234fug',
                        'tags': {'Name': 'gocd automation run'}
                    },
                    {
                        'ami_id': 'ami-puppydog',
                        'tags': {'Name': 'Normal Instance run by dogs'}
                    }
                ], 0, 'do_not_delete', {'tag:Name': 'gocd*'}, 1),

        (
                [
                    {
                        'ami_id': 'ami-1234fug',
                        'tags': {'Name': 'gocd automation run'}
                    },
                    {
                        'ami_id': 'ami-puppydog',
                        'tags': {'Name': 'Hamster_Dance_001 '}
                    }
                ], 1, 'do_not_delete', {'tag:Name': 'gocd*'}, 0),

        (
                [
                    {
                        'ami_id': 'ami-1234fug',
                        'tags': {'Name': 'gocd automation run', 'do_not_delete': 'true'}
                    },
                    {
                        'ami_id': 'ami-puppydog',
                        'tags': {'Name': 'Hamster_Dance_001'},
                    }
                ], 0, 'do_not_delete', {'tag:Name': 'gocd*'}, 0),

        (
                [
                    {
                        'ami_id': 'ami-1234fug',
                        'tags': {'Name': 'gocd automation run', 'do_not_delete': 'true'}
                    },
                    {
                        'ami_id': 'ami-puppydog',
                        'tags': {'Name': 'Hamster_Dance_001'},
                    }
                ], 1, 'do_not_delete', {'tag:Name': 'gocd*'}, 0),

        (
                [
                    {
                        'ami_id': 'ami-1234fug',
                        'tags': {'Name': 'gocd automation run 001'}
                    },
                    {
                        'ami_id': 'ami-puppydog',
                        'tags': {'Name': 'Hamster_Dance_001'},
                    },
                    {
                        'ami_id': 'ami-1234fug',
                        'tags': {'Name': 'gocd automation run 002'}
                    },
                ], 0, 'do_not_delete', {'tag:Name': 'gocd*'}, 2),
    )
    @ddt.unpack
    @mock_ec2
    def test_terminate_instances(self, instances, max_run_hours, skip_if_tag, tags, expected_count):
        conn = boto.connect_ec2('dummy_key', 'dummy_secret')
        for requested_instance in instances:
            reservation = conn.run_instances(requested_instance['ami_id'])
            for instance in reservation.instances:
                for key, val in requested_instance['tags'].items():
                    instance.add_tag(key, val)

        terminated_instances = ec2.terminate_instances(
            'us-east-1',
            max_run_hours=max_run_hours,
            skip_if_tag=skip_if_tag,
            tags=tags)
        self.assertEqual(len(terminated_instances), expected_count)
