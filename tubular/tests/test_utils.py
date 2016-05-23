import boto

from copy import copy
from boto.ec2.autoscale.launchconfig import LaunchConfiguration
from boto.ec2.autoscale.group import AutoScalingGroup
from boto.ec2.autoscale import Tag

def create_asg_with_tags(asg_name, tags, ami_id="ami-abcd1234", elbs=None):
    """
    Create an ASG with the given name, tags and AMI.  This is meant to be
    used in tests that are decorated with the @mock_autoscaling moto decorator.

    Arguments:
        asg_name(str): The name of the new auto-scaling group.
        tags(dict): A dict mapping tag names to tag values.
        ami_id(str): The ID of the AMI that should be deployed.

    Returns:
        boto.ec2.autoscale.group.AutoScalingGroup
    """

    tag_list = [ Tag(key=k, value=v) for k,v in tags.iteritems() ]

    if elbs is None:
        elbs = []

    # Create asgs
    conn = boto.ec2.autoscale.connect_to_region('us-east-1')
    config = LaunchConfiguration(
        name='{}_lc'.format(asg_name),
        image_id=ami_id,
        instance_type='t2.medium',
    )
    conn.create_launch_configuration(config)

    group = AutoScalingGroup(
        name=asg_name,
        availability_zones=['us-east-1c', 'us-east-1b'],
        default_cooldown=60,
        desired_capacity=2,
        load_balancers=elbs,
        health_check_period=100,
        health_check_type="EC2",
        max_size=2,
        min_size=2,
        launch_config=config,
        placement_group="test_placement",
        vpc_zone_identifier='subnet-1233abcd',
        termination_policies=["OldestInstance", "NewestInstance"],
        tags=tag_list,
    )
    conn.create_auto_scaling_group(group)
    return group

def create_elb(elb_name):
    boto_elb = boto.connect_elb()
    zones = ['us-east-1a', 'us-east-1b']
    ports = [(80, 8080, 'http'), (443, 8443, 'tcp')]
    lb = boto_elb.create_load_balancer(elb_name, zones, ports)
    instance_ids = ['i-4f8cf126', 'i-0bb7ca62']
    lb.register_instances(instance_ids)
    return lb


def clone_elb_instances_with_state(elb, state):
    """
        Shallow clone an ELB and gives the instances inside the state provided

        Arguments:
            elb(iterable): The ELB containing the instances
            state(string): The state the instances inside the ELB should have. Should be either "OutOfService"
                            or "InService"

        Returns: an elb object
    """
    elb_copy = copy(elb)
    for idx, instance in enumerate(elb):
        elb_copy[idx] = copy(instance)
        elb_copy[idx].state = state

    return elb_copy