#! /usr/bin/env python3

"""
Command-line script used to ensure the edxapp ASG is configured to dynamically
scale according to CPU load.

This script also inspects the all attached scaling policies and associated
alarms for extraneous triggers that might conflict with the resources installed
by this script.
"""
# pylint: disable=invalid-name
from __future__ import absolute_import
from __future__ import unicode_literals

from os import path
import sys
import logging
import traceback
import click
import yaml

# Add top-level module path to sys.path before importing tubular code.
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from tubular.utils import EDP  # pylint: disable=wrong-import-position
from tubular.ec2 import (  # pylint: disable=wrong-import-position
    asgs_for_edp,
    ensure_asg_scaling_policy,
    ensure_cloudwatch_alarm,
    describe_asg_scaling_policies,
    describe_cloudwatch_alarms,
)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)

# CONSTANTS
# These variables are common or merit explanation.

SCALING_UP_ALARM_NAME_FMT = '{asg_name}-cpu-scaling-up-trigger'.format
SCALING_DOWN_ALARM_NAME_FMT = '{asg_name}-cpu-scaling-down-trigger'.format

SCALING_UP_POLICY_NAME = 'scaling-up-policy'
SCALING_DOWN_POLICY_NAME = 'scaling-down-policy'

# Define the CPU utilization thresholds.  lower_utilization_threshold must
# be at most 2/3 of upper_utilization_threshold so that scaling from 3 to 2
# instances does not cause thrashing.  Assume 2 instances is the lower
# bound on the ASG.
UPPER_UTILIZATION_THRESHOLD = 60
LOWER_UTILIZATION_THRESHOLD = 35  # < 40 (i.e. 2/3 * 60)

# Derivation for scaling_up_adjustment:
#
# Model the total CPU utilized during an alarm breach as the product of the
# alarm breach threshold and the current instance count (N):
#
#     total CPU utilized = utilization_threshold * N
#
# Assume that scaling the instance count N by a scaling factor s does not
# change the total CPU utilized:
#
#     utilization_threshold * N = desired_utilization * N * s
#
# Solve for s:
#
#     s = utilization_threshold / desired_utilization
#       = 60 / 50
#       = 1.2
#
# Reinterpret the scaling factor s as a percent change in capacity:
#
#     adjustment = 100 * (s - 1.0)
#                = 20
#
SCALING_UP_ADJUSTMENT = 20  # percent of current capacity; see derivation above
SCALING_DOWN_ADJUSTMENT = -1  # whole instances; negative value implies scaling down


def configure_dynamic_scaling_for_edxapp_asg(asg_name, region):
    """
    Configure dynamic scaling for an exapp ASG.

    This immediately enables dynamic scaling if it wasn't already, which means
    if min and max ASG capacity are non-equal, instances may suddenly launch or
    terminate.

    Arguments:
        asg_name (string): Name of an edxapp ASG.

    Returns:
        (tuple of str): The ARNs for both the scaling-up and scaling-down
            policies.
    """
    # Install scaling policies
    common_scaling_policy_options = {
        'AutoScalingGroupName': asg_name,
        'PolicyType': 'SimpleScaling',
    }
    scaling_up_policy_options = {
        'PolicyName': SCALING_UP_POLICY_NAME,
        'AdjustmentType': 'PercentChangeInCapacity',
        'ScalingAdjustment': SCALING_UP_ADJUSTMENT,
        'Cooldown': 600,
    }
    scaling_down_policy_options = {
        'PolicyName': SCALING_DOWN_POLICY_NAME,
        'AdjustmentType': 'ChangeInCapacity',
        'ScalingAdjustment': SCALING_DOWN_ADJUSTMENT,
        'Cooldown': 300,
    }

    scaling_up_policy_options.update(common_scaling_policy_options)
    scaling_down_policy_options.update(common_scaling_policy_options)

    put_scaling_up_policy_response = ensure_asg_scaling_policy(region, **scaling_up_policy_options)
    put_scaling_down_policy_response = ensure_asg_scaling_policy(region, **scaling_down_policy_options)

    scaling_up_policy_arn = put_scaling_up_policy_response['PolicyARN']
    scaling_down_policy_arn = put_scaling_down_policy_response['PolicyARN']

    # Install scaling alarms (cloudwatch metric alarms)
    common_alarm_options = {
        'AlarmDescription': 'autoscaling trigger for {}'.format(asg_name),
        'ActionsEnabled': True,
        'MetricName': 'CPUUtilization',
        'Namespace': 'AWS/EC2',
        'Statistic': 'Average',
        'Period': 300,
        'Unit': 'Seconds',
        'EvaluationPeriods': 2,
        'Dimensions': [
            {
                'Name': 'AutoScalingGroupName',
                'Value': asg_name,
            },
        ],
    }
    scaling_up_alarm_options = {
        'AlarmName': SCALING_UP_ALARM_NAME_FMT(asg_name=asg_name),
        'AlarmActions': [scaling_up_policy_arn],
        'Threshold': UPPER_UTILIZATION_THRESHOLD,
        'ComparisonOperator': 'GreaterThanOrEqualToThreshold',
    }
    scaling_down_alarm_options = {
        'AlarmName': SCALING_DOWN_ALARM_NAME_FMT(asg_name=asg_name),
        'AlarmActions': [scaling_down_policy_arn],
        'Threshold': LOWER_UTILIZATION_THRESHOLD,
        'ComparisonOperator': 'LessThanOrEqualToThreshold',
    }

    scaling_up_alarm_options.update(common_alarm_options)
    scaling_down_alarm_options.update(common_alarm_options)

    ensure_cloudwatch_alarm(region, **scaling_up_alarm_options)
    ensure_cloudwatch_alarm(region, **scaling_down_alarm_options)

    return (scaling_up_policy_arn, scaling_down_policy_arn)


def validate_scaling_policy(scaling_policy, alarms_expected=None):
    """
    Validate the scaling policy.

    Arguments:
        scaling_policy (dict):
        alarms_expected (list of str): names of the only alarms we expect to be
            associated with the given policy.
    """
    if alarms_expected is None:
        alarms_expected = []
    for alarm in scaling_policy['Alarms']:
        if alarm['AlarmName'] not in alarms_expected:
            LOG.warning('Found an extraneous alarm attached to the "{}" scaling policy in the "{}" ASG: {} ({})'.format(
                scaling_policy['PolicyName'],
                scaling_policy['AutoScalingGroupName'],
                alarm['AlarmName'],
                alarm['AlarmARN'],
            ))


@click.command()
@click.option(
    '--region',
    help='aws region',
    default='us-east-1',
    type=str
)
@click.option(
    '--out_file',
    help='output file for the deploy information yaml',
    default=None
)
@click.option(
    '--environment',
    required=True,
    help='The name of the environment to attach scaling policies and alarms.',
)
def configure_dynamic_scaling(region, out_file, environment):
    """
    Primary entrypoint to this command.  See script docstring.
    """
    edxapp_edp = EDP(environment, 'edx', 'edxapp')
    edxapp_asg_prefix = '{}-{}-{}'.format(edxapp_edp.environment, edxapp_edp.deployment, edxapp_edp.play)
    try:
        asg_name_matches = asgs_for_edp(edxapp_edp, regex_filter=edxapp_asg_prefix)
        if len(asg_name_matches) > 1:
            click.secho('could not reliably determine the edxapp ASG name for the given environment.')
            sys.exit(1)
        asg_name = asg_name_matches[0]

        # Collect data about current state before making modifications.  These
        # functions will not error if the policies or alarms being asked for do
        # not exist yet, so a try/except block is not necessary.
        old_state = {
            'policies': describe_asg_scaling_policies(
                region,
                AutoScalingGroupName=asg_name,
                PolicyNames=[
                    SCALING_UP_POLICY_NAME,
                    SCALING_DOWN_POLICY_NAME
                ],
            )['ScalingPolicies'],
            'alarms': describe_cloudwatch_alarms(
                region,
                AlarmNames=[
                    SCALING_UP_ALARM_NAME_FMT(asg_name=asg_name),
                    SCALING_DOWN_ALARM_NAME_FMT(asg_name=asg_name),
                ],
            )['MetricAlarms'],
        }

        # Implement the changes!
        scaling_up_policy_arn, scaling_down_policy_arn = configure_dynamic_scaling_for_edxapp_asg(asg_name, region)

        # Intentionally ignore API paging because EC2 limits a single response to
        # 50 policies and we really don't ever expect to have more than 2.
        scaling_policies = describe_asg_scaling_policies(
            region,
            AutoScalingGroupName=asg_name
        )['ScalingPolicies']

        # Validate all policies and alarms for this ASG
        scaling_up_policy = None
        scaling_down_policy = None
        for policy in scaling_policies:
            if policy['PolicyARN'] == scaling_up_policy_arn:
                scaling_up_policy = policy
            elif policy['PolicyARN'] == scaling_down_policy_arn:
                scaling_down_policy = policy
            else:
                # Report extraneous scaling policies
                LOG.warning('Found an extraneous scaling policy in the "{}" ASG: {} ({}).'.format(
                    asg_name,
                    policy['PolicyName'],
                    policy['PolicyARN'],
                ))

        # Report extraneous cloudwatch alarms
        validate_scaling_policy(scaling_up_policy, alarms_expected=[SCALING_UP_ALARM_NAME_FMT(asg_name=asg_name)])
        validate_scaling_policy(scaling_down_policy, alarms_expected=[SCALING_DOWN_ALARM_NAME_FMT(asg_name=asg_name)])

        # Collect data about state after modifications
        new_state = {
            'policies': [
                scaling_up_policy,
                scaling_down_policy,
            ],
            'alarms': describe_cloudwatch_alarms(
                region,
                AlarmNames=[
                    SCALING_UP_ALARM_NAME_FMT(asg_name=asg_name),
                    SCALING_DOWN_ALARM_NAME_FMT(asg_name=asg_name),
                ],
            )['MetricAlarms'],
        }
    except Exception as e:  # pylint: disable=broad-except
        traceback.print_exc()
        click.secho('Unable to configure dynamic scaling: {0} - {1}'.format(asg_name, e), fg='red')
        sys.exit(1)
    with open(out_file, mode='x') as out_file_stream:
        yaml.dump(
            {
                'old_state': old_state,
                'new_state': new_state,
            },
            stream=out_file_stream,
        )
    sys.exit(0)

if __name__ == "__main__":
    configure_dynamic_scaling()  # pylint: disable=no-value-for-parameter
