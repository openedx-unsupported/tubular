import logging
import time
import sys
from kubernetes.client.rest import ApiException
from kubernetes import client, config


logging.basicConfig(stream=sys.stdout, level=logging.INFO)
LOG = logging.getLogger(__name__)


def create_job_object(name, command, args_command, deployment_specs_container, deployment_specs,
                      cpu_request, memory_request, cpu_limit, memory_limit):
    try:
        # Configured Pod template container
        container = client.V1Container(
            name=name,
            image=deployment_specs_container.image,
            env=deployment_specs_container.env,
            command=command.split(" "),
            args=[args_command],
            liveness_probe=deployment_specs_container.liveness_probe,
            ports=deployment_specs_container.ports,
            readiness_probe=deployment_specs_container.readiness_probe,
            volume_mounts=deployment_specs_container.volume_mounts,
            resources=client.V1ResourceRequirements(
                # minimum amount of compute resources required
                requests={"cpu": cpu_request, "memory": memory_request},
                # maximum amount of compute resources allowed
                limits={"cpu": cpu_limit, "memory": memory_limit}
            )
        )
        # Create and Configured a spec section
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": name}),
            spec=client.V1PodSpec(restart_policy="Never",
                                  containers=[container],
                                  volumes=deployment_specs.volumes,
                                  init_containers=deployment_specs.init_containers,
                                  service_account_name=deployment_specs.service_account_name))
        # Create the specification of deployment
        spec = client.V1JobSpec(
            template=template,
            backoff_limit=4)
        # Instantiate the job object
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(name=name),
            spec=spec)
        return job
    except ApiException as e:
        LOG.error("Exception: %s\n" % e)
        sys.exit(1)


def create_job(k8s_client, job, namespace):
    try:
        api_response = k8s_client.create_namespaced_job(
            body=job,
            namespace=namespace)
        LOG.info("Job created. status='%s'" % str(api_response.status))
    except ApiException as e:
        LOG.error("Exception when calling BatchV1Api->create_namespaced_job: %s\n" % e)
        sys.exit(1)


def delete_job(k8s_client, name, namespace):
    try:
        api_response = k8s_client.delete_namespaced_job(
            name=name,
            namespace=namespace,
            body=client.V1DeleteOptions(
                propagation_policy='Foreground',
                grace_period_seconds=5))
        LOG.info("Job deleted. status='%s'" % str(api_response.status))
    except ApiException as e:
        LOG.error("Exception when calling BatchV1Api->create_namespaced_job: %s\n" % e)
        sys.exit(1)


def get_deployment(configuration, namespace, deployment_name):
    try:
        apis_api = client.AppsV1Api(client.ApiClient(configuration))
        resp = apis_api.read_namespaced_deployment(deployment_name, namespace)
        return resp.spec.template.spec
    except ApiException as e:
        LOG.error("Exception: %s\n" % e)
        sys.exit(1)


def get_logs(k8s_client, job_name, namespace):
    job_def = k8s_client.read_namespaced_job(name=job_name, namespace=namespace)
    controller_uid = job_def.metadata.labels["controller-uid"]
    core_v1 = client.CoreV1Api()
    pod_label_selector = "controller-uid=" + controller_uid
    pods_list = core_v1.list_namespaced_pod(
        namespace=namespace,
        label_selector=pod_label_selector,
        timeout_seconds=10
    )
    pod_name = pods_list.items[0].metadata.name
    while True:
        pod_status = core_v1.read_namespaced_pod_status(name=pod_name, namespace=namespace)
        if pod_status.status.phase != "Running" and pod_status.status.phase != "Succeeded":
            time.sleep(5)
        else:
            break
    try:
        for line in core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                follow=True,
                _preload_content=False
        ).stream():
            LOG.info(line.decode('utf-8'))
    except client.rest.ApiException as e:
        LOG.error("Exception when calling CoreV1Api->read_namespaced_pod_log: %s\n" % e)
        sys.exit(1)


def check_create_args(new_relic_args, deployment_args, command_args):
    try:
        for args in new_relic_args:
            new_relic_args_check = any(args in string for string in deployment_args)
            if new_relic_args_check:
                continue
            else:
                return command_args
        command_args = deployment_args[0] + " && " + command_args
        return command_args
    except Exception as e:
        LOG.error("Unable to make args for kubernetes job " + str(e))
        sys.exit(1)
