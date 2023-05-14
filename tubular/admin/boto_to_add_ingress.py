#!/usr/bin/env python3

"""
Command-line script which, for each ASG (app) in each VPC, adds a rule to each SG associated
with the ASG's launch configuration that allows SSH ingress from the GoCD agents' SG.
"""

import logging
import six

import click
import boto3
from botocore.exceptions import ClientError

LOG_FILENAME = 'security_group_change.txt'
logging.basicConfig(level=logging.INFO)


@click.command("add_ingress_rule")
@click.option(
    '--dry-run',
    is_flag=True,
    help='Perform a dry run of the rule addition.',
)
@click.option(
    '--go-agent-security-group',
    help='The security group id of the go-agent cluster.',
)
@click.option(
    '--go-agent-security-group-owner',
    help='The account id for the aws account the go-agent is in.',
)
@click.option(
    '--go-agent-security-group-name',
    default=u'prod-tools-goagent-sg',
    help='The security group name for the go-agent cluster.',
)
def add_ingress_rule(dry_run, go_agent_security_group, go_agent_security_group_owner, go_agent_security_group_name):
    """
    For each ASG (app) in each VPC, add a rule to each SG associated with the ASG's launch configuration
    that allows SSH ingress from the GoCD agents' SG.

    BEFORE RUNNING THIS SCRIPT!:
    - Use the assume_role bash script to assume the role in the proper account/VPC (edx, edge, mckinsey, etc.)
        - If you don't know what this is, ask someone in DevOps.
    - THEN run this script.
    """
    asg_conn = boto3.client('autoscaling')
    ec2 = boto3.client('ec2', region_name='us-east-1')

    asgs = []
    launch_configs = {}
    security_groups = {}

    response_auto_scalling_group = asg_conn.describe_auto_scaling_groups()
    logging.debug('All ASGs:')
    for group in response_auto_scalling_group['AutoScalingGroups']:
        logging.debug('    {}'.format(group['AutoScalingGroupName']))
        asgs.append(group)

    response_launch_config = asg_conn.describe_launch_configurations()
    logging.debug('All launch configurations:')
    for launch_config in response_launch_config['LaunchConfigurations']:
        logging.debug('    {}'.format(launch_config['LaunchConfigurationName']))
        launch_configs[launch_config['LaunchConfigurationName']] = launch_config

    logging.debug('All security groups:')
    response = ec2.describe_security_groups()
    for sec_group in response['SecurityGroups']:
        logging.debug('    {}'.format(sec_group))
        security_groups[sec_group['GroupId']] = sec_group

    # Validate that each ASG has a launch configuration.
    for group in asgs:
        try:
            logging.info("Launch configuration for ASG '{}' is '{}'.".format(
                group['AutoScalingGroupName'], launch_configs[group['LaunchConfigurationName']]
            ))
        except KeyError:
            logging.error("Launch configuration '{}' for ASG '{}' was not found!".format(
                group['LaunchConfigurationName'], group['AutoScalingGroupName']
            ))
            raise

    # Construct a fake security group for the prod-tools-goagent-sg security group in the edx-tools account.
    # This group will be used to grant the go-agents ingress into the ASG's VPCs.
    go_agent_security_group = ec2.create_security_group(
        GroupName=go_agent_security_group_name,
        Description='Fake security group for the prod-tools-goagent-sg security group in the edx-tools account',
    )

    # For each launch config, check for the security group. Can support multiple security groups
    # but the edX DevOps convention is to use a single security group.

    for group in asgs:
        launch_config = launch_configs[group['LaunchConfigurationName']]
        if len(launch_config['SecurityGroups']) > 1:
            err_msg = "Launch config '{}' for ASG '{}' has more than one security group!: {}".format(
                launch_config['LaunchConfigurationName'],
                group['AutoScalingGroupName'],
                launch_config['SecurityGroups']
            )
            logging.warning(err_msg)
            continue

        sg_name = launch_config['SecurityGroups'][0]
        try:
            # Find the security group.
            sec_group = security_groups[sg_name]
        except KeyError:
            logging.error("Security group '{}' for ASG '{}' was not found!.".format(
                sg_name, group['AutoScalingGroupName']))
        logging.info(
            'BEFORE: Rules for security group {}:'.format(sec_group['GroupName']))
        logging.info(sec_group['IpPermissions'])
        try:
            # Add the ingress rule to the security group.
            yes_no = six.moves.input("Apply the change to this security group? [Yes]")
            if yes_no in ("", "y", "Y", "yes"):
                # ssh access
                ec2.authorize_security_group_ingress(
                    GroupId=go_agent_security_group['GroupId'],
                    DryRun=dry_run,
                    IpPermissions=[
                        {
                            'IpProtocol': 'tcp',
                            'FromPort': 22,
                            'ToPort': 22,
                        }
                    ]
                )
        except ClientError as exc:
            if exc.response['ResponseMetadata']['HTTPStatusCode'] == 412:
                # If the dry_run flag is set, then each rule addition will raise this exception.
                # Log it and carry on.
                logging.info('Dry run is True but rule addition would have succeeded for security group {}.'.format(
                    sg_name
                ))
            elif exc.response['Error']['Code'] == 'InvalidPermission.Duplicate':
                logging.info("Rule already exists for {}.".format(sg_name))
            else:
                logging.info("Error appeared with code {}.".format(exc.response['Error']['Code']))
                raise

        logging.info('AFTER: Rules for security group {}:'.format(sg_name))
        logging.info(sec_group['IpPermissions'])

if __name__ == "__main__":
    add_ingress_rule()  # pylint: disable=no-value-for-parameter
