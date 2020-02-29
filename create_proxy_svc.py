"""
Create proxy service for a given kube service's cluster ip and port
"""
import datetime
import os
import tempfile
from jinja2 import Template
from kubernetes import config, client
from mongoengine import connect
import yaml
import models

MONGODB = "mongodb://localhost/sbf"
connect(host=MONGODB)

proxy_deployment_template = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{proxy_name}}
spec:
  selector:
    matchLabels:
      run: {{proxy_name}}
  replicas: 2
  template:
    metadata:
      labels:
        run: {{proxy_name}}
    spec:
      containers:
      - name: {{proxy_name}}
        image: nginx
        ports:
        - containerPort: 80
        volumeMounts:
        - name: nginx-conf
          mountPath: /etc/nginx/nginx.conf
          subPath: nginx.conf
      volumes:
      - name: nginx-conf
        configMap:
          name: {{proxy_name}}
"""

proxy_service_template = """
apiVersion: v1
kind: Service
metadata:
  name: {{proxy_name}}
spec:
  type: LoadBalancer
  ports:
  - port: 80
    protocol: TCP
  selector:
    run: {{proxy_name}}
"""

proxy_config_template = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{proxy_name}}
data:
  nginx.conf: |
    {{proxy_nginx_data | indent(4)}}
"""


def create_proxy_config(app_svc):
    upstream = app_svc.cluster_ip + ":" + str(app_svc.ports[0]['port'])
    nginx_data = Template(open('nginx.conf').read()).render(cluster_ip_port=upstream)
    t = Template(proxy_config_template)
    config_name = "proxy-" + app_svc.name
    body = t.render(proxy_name=config_name, proxy_nginx_data=nginx_data)
    body = yaml.safe_load(body)
    v1 = client.CoreV1Api()
    try:
        v1.create_namespaced_config_map(body=body, namespace=app_svc.namespace)
    except client.rest.ApiException as e:
        if e.reason == "Conflict":
            v1.patch_namespaced_config_map(
                name=config_name, body=body, namespace=app_svc.namespace)
        else:
            raise(e)


def create_proxy_deployment(app_svc):
    # create a pod that reverse proxies to the app_svc
    t = Template(proxy_deployment_template)
    deployment_name = "proxy-" + app_svc.name
    body = t.render(proxy_name=deployment_name)
    body = yaml.safe_load(body)
    v1 = client.AppsV1Api()
    try:
        v1.create_namespaced_deployment(body=body, namespace=app_svc.namespace)
    except client.rest.ApiException as e:
        if e.reason == "Conflict":
            v1.patch_namespaced_deployment(
                name=deployment_name, body=body, namespace=app_svc.namespace)
        else:
            raise(e)


def create_proxy_svc(app_svc):
    # create svc for the proxy pods created
    deployment_name = "proxy-" + app_svc.name
    svc_name = "proxy-%s" % app_svc.name
    t = Template(proxy_service_template)
    body = t.render(proxy_name=deployment_name)
    body = yaml.safe_load(body)
    v1 = client.CoreV1Api()
    rsp = None
    try:
        rsp = v1.create_namespaced_service(
            body=body, namespace=app_svc.namespace)
    except client.rest.ApiException as e:
        if e.reason == "Conflict":
            rsp = v1.patch_namespaced_service(
                name=svc_name, body=body, namespace=app_svc.namespace)
        else:
            raise(e)
    return rsp


def update_svc(app_svc, proxy_svc):
    # app_svc.proxy_date_deployed = datetime.datetime.utcnow()
    app_svc.proxy_svc_name = proxy_svc.metadata.name
    if proxy_svc.spec.load_balancer_ip:
        app_svc.proxy_ip = proxy_svc.spec.load_balancer_ip
    else:
        addr_list = get_node_ips()
        app_svc.proxy_ip = addr_list
        app_svc.proxy_port = proxy_svc.spec.ports[0].node_port
    app_svc.save()


def get_node_ips():
    v1 = client.CoreV1Api()
    addr_list = []
    for node in v1.list_node().items:
        for addr in node.status.addresses:
            addr_list.append(addr.address)
    return addr_list


def protect_service(app_svc):
    kube_profile = models.KubeProfile.objects(name=app_svc.kube_profile).get()
    tmp_fd, tmp_file_name = tempfile.mkstemp(text=True)
    fd = os.fdopen(tmp_fd, "w")
    fd.write(kube_profile.kube_config)
    fd.close()
    config.load_kube_config(tmp_file_name)
    create_proxy_config(app_svc)
    create_proxy_deployment(app_svc)
    rsp = create_proxy_svc(app_svc)
    update_svc(app_svc, rsp)


def protect_services():
    # svc must not have been deployed or date_modified is greater than date_deployed
    query = {
        "$or": [
            {"$expr": {"$gt": ["$date_modified", "$proxy_date_deployed"]}},
            {"proxy_date_deployed": ""}
        ]
    }
    for svc in models.Service.objects(__raw__=query):
        protect_service(svc)


if __name__ == "__main__":
    protect_services()
