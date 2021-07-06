import click
import sys
from tubular.kubernetes import *


@click.command()
@click.option(
    '--cluster_name',
    required=True,
    help="k8s cluster name.",
)
@click.option(
    '--cluster_arn',
    required=True,
    help="k8s cluster ARN.",
)
@click.option(
    '--deployment_name',
    required=True,
    help="Deployment name use to create job.",
)
@click.option(
    '--namespace',
    required=True,
    help="Namespace in which create the job."
)
@click.option(
    '--command',
    required=True,
    help="Command to run in job.",
)
@click.option(
    '--command_args',
    required=False,
    help="Args pass to command that run in the job.",
)
@click.option(
    '--cpu_limit',
    required=False,
    help="Maximum amount of CPU resources allowed.",
)
@click.option(
    '--memory_limit',
    required=False,
    help="Maximum amount of memory resources allowed.",
)
def create_k8s_job(cluster_name, cluster_arn, deployment_name, namespace, command, command_args, cpu_limit, memory_limit):
    """
    Create the k8s job in given namespace.
    """
    new_relic_args = ["source /vault-api-secrets/secrets/secret.env", "newrelic-admin"]
    # Setting Configuration
    api_token = get_token(cluster_name)
    api_token = api_token.decode("utf-8")
    configuration = client.Configuration()
    configuration.host = cluster_arn
    configuration.verify_ssl = False
    configuration.debug = True
    configuration.api_key['authorization'] = "Bearer " + api_token
    configuration.assert_hostname = True
    configuration.verify_ssl = False
    client.Configuration.set_default(configuration)

    deployment_specs = get_deployment(configuration, namespace, deployment_name)
    deployment_specs_container = deployment_specs.containers[0]
    cpu_request = deployment_specs_container.resources.requests["cpu"]
    memory_request = deployment_specs_container.resources.requests["memory"]
    if not cpu_limit:
        cpu_limit = deployment_specs_container.resources.limits["cpu"]
    if not memory_limit:
        memory_limit = deployment_specs_container.resources.limits["memory"]
    command_args = check_create_args(new_relic_args, deployment_specs_container.args, command_args)
    config.load_kube_config()
    k8s_client = client.BatchV1Api()
    job = create_job_object(deployment_name, command, command_args, deployment_specs_container,
                            deployment_specs, cpu_request, memory_request, cpu_limit, memory_limit)
    create_job(k8s_client, job, namespace)
    get_logs(k8s_client, deployment_name, namespace)
    delete_job(k8s_client, deployment_name, namespace)
    # An exit code of 0 means success and non-zero means failure.
    sys.exit(0)


if __name__ == '__main__':
    create_k8s_job()
