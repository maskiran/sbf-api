"""
Create proxy service for a given kube service's cluster ip and port
"""
import os
import tempfile
from kubernetes import config, client
from mongoengine import connect
import models

MONGODB = "mongodb://localhost/sbf"
connect(host=MONGODB)

def create_deployment_object(app_svc):
    # Configureate Pod template container
    container = client.V1Container(
        name="proxy-nginx-for-%s" % app_svc.name,
        image="nginx",
        ports=[client.V1ContainerPort(container_port=80)])
    # Create and configurate a spec section
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"proxy": app_svc.name}),
        spec=client.V1PodSpec(containers=[container]))
    # Create the specification of deployment
    spec = client.V1DeploymentSpec(
        replicas=2,
        template=template,
        selector={'matchLabels': {'proxy': app_svc.name}})
    # Instantiate the deployment object
    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name="proxy-deployment-%s" % app_svc.name),
        spec=spec)

    return deployment


def create_proxy_deployment(app_svc):
    # create a pod that reverse proxies to the app_svc
    body = create_deployment_object(app_svc)
    v1 = client.AppsV1Api()
    try:
        v1.create_namespaced_deployment(body=body, namespace=app_svc.namespace)
    except client.rest.ApiException as e:
        if e.reason == "Conflict":
            v1.patch_namespaced_deployment(name=body.metadata.name, body=body, namespace=app_svc.namespace)


def create_proxy_svc(app_svc):
    # create svc for the proxy pods created
    svc_name = "proxy-svc-%s" % app_svc.name
    body = client.V1Service()
    body.metadata = client.V1ObjectMeta(name=svc_name)
    body.spec = client.V1ServiceSpec(type="LoadBalancer",
        ports=[{'port': 80}],
        selector={'proxy': app_svc.name})
    v1 = client.CoreV1Api()
    try:
        v1.create_namespaced_service(body=body, namespace=app_svc.namespace)
    except client.rest.ApiException as e:
        if e.reason == "Conflict":
            v1.patch_namespaced_service(name=svc_name, body=body, namespace=app_svc.namespace)


def protect_services():
    # svc must not have been deployed
    for svc in models.Service.objects(proxy_date_deployed=None, proxy_policy_profile__ne=None):
        print('Protecting', svc.name)
        kube_profile = models.KubeProfile.objects(name=svc.kube_profile).get()
        tmp_fd, tmp_file_name = tempfile.mkstemp(text=True)
        fd = os.fdopen(tmp_fd, "w")
        fd.write(kube_profile.kube_config)
        fd.close()
        config.load_kube_config(tmp_file_name)
        create_proxy_deployment(svc)
        create_proxy_svc(svc)


if __name__ == "__main__":
    protect_services()        
