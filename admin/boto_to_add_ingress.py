#!/usr/bin/env python
import sys
from os import path
import click
import logging
import boto.ec2
from boto.ec2.autoscale import AutoScaleConnection


LOG_FILENAME = 'security_group_change.txt'
logging.basicConfig(filename=LOG_FILENAME,level=logging.INFO)

# Info for the security group used by the go-agents.
GO_AGENT_SECURITY_GROUP_NAME = u'prod-tools-goagent-sg'
# The values below are fake - replace them with the real values.
GO_AGENT_SECURITY_GROUP_OWNER_ID = 111111111111
GO_AGENT_SECURITY_GROUP_ID = u'sg-beefbeef'


@click.command()
@click.option(
    '--dry-run',
    is_flag=True,
    help='Perform a dry run of the rule addition.',
)
def add_ingress_rule(dry_run):
    """
    For each ASG (app) in each VPC, add a rule to each SG associated with the ASG's launch configuration
    that allows SSH ingress from the GoCD agents' SG.

    BEFORE RUNNING THIS SCRIPT!:
    - Use the assume_role bash script to assume the role in the proper account/VPC (edx, edge, mckinsey, etc.)
        - If you don't know what this is, ask someone in DevOps.
    - THEN run this script.
    """
    asg_conn = AutoScaleConnection()
    ec2_conn = boto.ec2.connect_to_region('us-east-1')
    asgs = []
    launch_configs = {}
    security_groups = {}

    logging.debug('All ASGs:')
    for group in asg_conn.get_all_groups():
        logging.debug('    {}'.format(group))
        asgs.append(group)

    logging.debug('All launch configurations:')
    for lc in asg_conn.get_all_launch_configurations():
        logging.debug('    {}'.format(lc))
        launch_configs[lc.name] = lc

    logging.debug('All security groups:')
    for sg in ec2_conn.get_all_security_groups():
        logging.debug('    {}'.format(sg))
        security_groups[sg.id] = sg

    # Validate that each ASG has a launch configuration.
    for group in asgs:
        try:
            logging.info("Launch configuration for ASG '{}' is '{}'.".format(
                group.name, launch_configs[group.launch_config_name]
            ))
        except KeyError:
            logging.error("Launch configuration '{}' for ASG '{}' was not found!".format(
                group.launch_config_name, group.name
            ))
            raise

    # Construct a fake security group for the prod-tools-goagent-sg security group in the edx-tools account.
    # This group will be used to grant the go-agents ingress into the ASG's VPCs.
    go_agent_security_group = boto.ec2.securitygroup.SecurityGroup(
        name=GO_AGENT_SECURITY_GROUP_NAME,
        owner_id=GO_AGENT_SECURITY_GROUP_OWNER_ID,
        id=GO_AGENT_SECURITY_GROUP_ID
    )

    # For each launch config, check for the security group. Can support multiple security groups
    # but the edX DevOps convention is to use a single security group.
    for group in asgs:
        launch_config = launch_configs[group.launch_config_name]
        if len(launch_config.security_groups) > 1:
            err_msg = "Launch config '{}' for ASG '{}' has more than one security group!: {}".format(
                launch_config.name, group.name, launch_config.security_groups
            )
            logging.warning(err_msg)
            continue
        sg_name = launch_config.security_groups[0]
        try:
            # Find the security group.
            sg = security_groups[sg_name]
        except KeyError:
            logging.error("Security group '{}' for ASG '{}' was not found!.".format(sg_name, group.name))
        logging.info('BEFORE: Rules for security group {}:'.format(sg_name))
        logging.info(sg.rules)
        try:
            # Add the ingress rule to the security group.
            sg.authorize(src_group=go_agent_security_group, dry_run=dry_run)
        except boto.exception.EC2ResponseError as exc:
            if exc.status == 412:
                # If the dry_run flag is set, then each rule addition will raise this exception.
                # Log it and carry on.
                logging.info('Dry run is True but rule addition would have succeeded for security group {}.'.format(sg_name))
            else:
                raise
        logging.info('AFTER: Rules for security group {}:'.format(sg_name))
        logging.info(sg.rules)



if __name__ == "__main__":
    add_ingress_rule()
