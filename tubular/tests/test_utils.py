"""
Tests of the utility code.
"""

from copy import copy
import six
import boto3
from moto import mock_ec2


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

    tag_list = [
        {
            'Key': k,
            'Value': v,
            'ResourceType': 'auto-scaling-group',
            'ResourceId': asg_name
        } for k, v in six.iteritems(tags)
    ]

    if elbs is None:
        elbs = []

    boto3.resource('ec2')
    ec2_client = boto3.client('ec2')
    vpc = ec2_client.create_vpc(CidrBlock='10.0.0.0/24')
    subnet1 = ec2_client.create_subnet(VpcId=vpc['Vpc']['VpcId'], CidrBlock='10.0.0.0/28', AvailabilityZone='us-east-1c')
    subnet2 = ec2_client.create_subnet(VpcId=vpc['Vpc']['VpcId'], CidrBlock='10.0.0.16/28', AvailabilityZone='us-east-1b')
    autoscale = boto3.client("autoscaling")

    autoscale.create_launch_configuration(
        LaunchConfigurationName="tester",
        ImageId=ami_id,
        InstanceType="t2.medium",
    )
    launch_config = autoscale.describe_launch_configurations()["LaunchConfigurations"][0]
    autoscale.create_auto_scaling_group(
        AutoScalingGroupName=asg_name,
        AvailabilityZones=['us-east-1c', 'us-east-1b'],
        DefaultCooldown=60,
        DesiredCapacity=2,
        HealthCheckGracePeriod=100,
        HealthCheckType="EC2",
        MaxSize=3,
        MinSize=2,
        LaunchConfigurationName=launch_config["LaunchConfigurationName"],
        PlacementGroup="test_placement",
        TerminationPolicies=["OldestInstance", "NewestInstance"],
        VPCZoneIdentifier='{0},{1}'.format(subnet1['Subnet']['SubnetId'], subnet2['Subnet']['SubnetId']),
    )

    # Each ASG tag that has 'propagate_at_launch' set to True is *supposed* to be set on the instances.
    # However, it seems that moto (as of 0.4.30) does not properly set the tags on the instances created by the ASG.
    # So set the tags on the ASG instances manually instead.
    response = autoscale.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
    # assert response['AutoScalingGroups'][0]['LaunchConfigurationName'] == launch_config_name
    assert response["AutoScalingGroups"][0]["MinSize"] == 2
    assert response["AutoScalingGroups"][0]["MaxSize"] == 3

    autoscale.create_or_update_tags(
        Tags=tag_list
    )


def create_elb(elb_name):
    """
    Method to create an Elastic Load Balancer.
    """

    boto_elb = boto3.client('elb')
    zones = ['us-east-1a', 'us-east-1b']
    ports = [
        {
            'LoadBalancerPort': 80,
            'InstancePort': 8080,
            'Protocol': 'HTTP'
        },
        {
            'LoadBalancerPort': 443,
            'InstancePort': 8443,
            'Protocol': 'TCP'
        }
    ]

    load_balancer = boto_elb.create_load_balancer(
        LoadBalancerName=elb_name,
        AvailabilityZones=zones,
        Listeners=ports
    )

    instance_ids = ['i-4f8cf126', 'i-0bb7ca62']
    boto_elb.register_instances_with_load_balancer(
        LoadBalancerName=elb_name,
        Instances=[
            {'InstanceId': instance_id} for instance_id in instance_ids
        ]
    )

    return boto_elb.describe_instance_health(
        LoadBalancerName=elb_name,
        Instances=[{'InstanceId': instance_id} for instance_id in instance_ids]
    )["InstanceStates"]


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
    for idx, instance in enumerate(elb['InstanceStates']):
        elb_copy[idx] = copy(instance)
        elb_copy[idx]['State'] = state
    return elb_copy
