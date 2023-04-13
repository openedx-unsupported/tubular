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
            "PropagateAtLaunch": True,
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
    
    security_group1 = ec2_client.create_security_group(
        GroupName=asg_name, Description=f"{asg_name}-desc details."
    )

    autoscale.create_launch_configuration(
        LaunchConfigurationName="tester",
        ImageId=ami_id,
        InstanceType="t2.medium",
        SecurityGroups=[security_group1['GroupId']]

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
        Tags=tag_list,
        LoadBalancerNames=elbs,
    )

    autoscale.create_or_update_tags(
        Tags=tag_list
    )

    ec2_client.authorize_security_group_ingress(
        GroupId=security_group1['GroupId'],
        IpProtocol='tcp',
        FromPort=80,
        ToPort=80,
        CidrIp='10.0.0.0/24'
    )

    # fill the rules up the limit
    permissions = [
        {
            "IpProtocol": "-1",
            "IpRanges": [{"CidrIp": f"{i}.0.0.0/0"} for i in range(10 - 1)],
        }
    ]
    ec2_client.authorize_security_group_ingress(
        GroupId=security_group1['GroupId'], IpPermissions=permissions
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

    boto_elb.create_load_balancer(
        LoadBalancerName=elb_name,
        AvailabilityZones=zones,
        Listeners=ports
    )

    instance_ids = ['i-4f8cf126', 'i-0bb7ca62']
    boto_elb.register_instances_with_load_balancer(
        LoadBalancerName=elb_name,
        Instances=[
            {
                'InstanceId': instance_id
            }
            for instance_id in instance_ids
        ]
    )

    response = boto_elb.describe_instance_health(LoadBalancerName=elb_name)
    assert sorted([ins['InstanceId'] for ins in response['InstanceStates']]) == sorted(instance_ids)
    return elb_name


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
