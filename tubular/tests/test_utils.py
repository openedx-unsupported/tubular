"""
Tests of the utility code.
"""

from copy import copy
import six
import boto3


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

    if elbs is None:
        elbs = []

    ec2 = boto3.client('ec2')

    vpc = ec2.create_vpc(CidrBlock='10.0.0.0/24')
    subnetc = ec2.create_subnet(VpcId=vpc['Vpc']['VpcId'], CidrBlock='10.0.0.0/28', AvailabilityZone='us-east-1c')
    subnetb = ec2.create_subnet(VpcId=vpc['Vpc']['VpcId'], CidrBlock='10.0.0.16/28', AvailabilityZone='us-east-1b')
    autoscale = boto3.client('autoscaling')

    # ec2_res = boto3.resource("ec2", "us-east-1")
    # ec2_client = boto3.client("ec2", region_name="us-east-1")
    autoscale = boto3.client("autoscaling", region_name="us-east-1")

    # random_image_id = ec2_client.describe_images()["Images"][0]["ImageId"]
    dummy_ami_id = 'ami-12c6146b'

    autoscale.create_launch_configuration(
        LaunchConfigurationName="tester",
        ImageId=dummy_ami_id,
        InstanceType="t1.micro",
    )

    launch_config = autoscale.describe_launch_configurations()["LaunchConfigurations"][0]

    autoscale.create_auto_scaling_group(
        AutoScalingGroupName=asg_name,
        AvailabilityZones=['us-east-1a', 'us-east-1b'],
        DefaultCooldown=60,
        DesiredCapacity=2,
        LoadBalancerNames=['healthy-lb-1'],
        HealthCheckGracePeriod=100,
        HealthCheckType="EC2",
        MaxSize=3,
        MinSize=2,
        LaunchConfigurationName=launch_config["LaunchConfigurationName"],
        PlacementGroup="test_placement",
        TerminationPolicies=["OldestInstance", "NewestInstance"],
    )

    # Each ASG tag that has 'propagate_at_launch' set to True is *supposed* to be set on the instances.
    # However, it seems that moto (as of 0.4.30) does not properly set the tags on the instances created by the ASG.
    # So set the tags on the ASG instances manually instead.
    response = autoscale.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
    # assert response['AutoScalingGroups'][0]['LaunchConfigurationName'] == launch_config_name
    assert response["AutoScalingGroups"][0]["MinSize"] == 2
    assert response["AutoScalingGroups"][0]["MaxSize"] == 3

    tag_list = [
        {
            'Key': k,
            'Value': v,
            'ResourceType': 'auto-scaling-group',
            'ResourceId': asg_name
        } for k, v in six.iteritems(tags)
    ]

    # asg = autoscale.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])
    autoscale.create_or_update_tags(
        Tags=tag_list
    )

    # asg_tags = autoscale.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])["AutoScalingGroups"]
    # return asg_tags[0]['Tags']


def create_elb(elb_name):
    """
    Method to create an Elastic Load Balancer.
    """
    import pdb;
    pdb.set_trace()
    boto_elb = boto3.client('elb', region_name="us-east-1")
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

    res_instances = boto_elb.register_instances_with_load_balancer(
        LoadBalancerName=elb_name,
        Instances=[
            {'InstanceId': instance_id} for instance_id in instance_ids
        ]
    )

    return res_instances


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
