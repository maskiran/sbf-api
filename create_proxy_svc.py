"""
Create proxy service for a given kube service's cluster ip and port
"""
import base64
import datetime
import os
import shutil
import tarfile
import tempfile
from jinja2 import Template
from kubernetes import config, client
import yaml
import models

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
        updated: {{date_time}}
    spec:
      initContainers:
      - name: setup-rules
        image: alpine
        volumeMounts:
        - name: rules-tgz
          mountPath: /rules
        - name: crs-rules
          mountPath: /crs-rules
        command: ['tar', '-zxf', '/rules/rules.tgz', '-C', '/crs-rules']
      containers:
      - name: {{proxy_name}}
        image: owasp/modsecurity:3.0-nginx
        ports:
        - containerPort: 80
        volumeMounts:
        - name: nginx-conf
          mountPath: /etc/nginx/nginx.conf
          subPath: nginx.conf
        - name: nginx-conf
          mountPath: /etc/modsecurity.d/modsecurity.conf
          subPath: modsecurity.conf
        - name: nginx-conf
          mountPath: /etc/modsecurity.d/include.conf
          subPath: include.conf
        - name: nginx-conf
          mountPath: /etc/modsecurity.d/crs/crs-setup.conf
          subPath: crs-setup.conf
        - name: crs-rules
          mountPath: /etc/modsecurity.d/crs/rules
      volumes:
      - name: nginx-conf
        configMap:
          name: {{proxy_name}}
      - name: rules-tgz
        secret:
          secretName: {{proxy_name}}
      - name: crs-rules
        emptyDir: {}
"""

proxy_service_template = """
apiVersion: v1
kind: Service
metadata:
  name: {{proxy_name}}
  labels:
    type: sbf-proxy
spec:
  type: LoadBalancer
  externalTrafficPolicy: Local
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
    {{nginx_conf | indent(4)}}
  include.conf: |
    {{modsec_include | indent(4)}}
  modsecurity.conf: |
    {{modsec_conf | indent(4)}}
  crs-setup.conf: |
    {{crs_setup_conf | indent(4)}}
"""

proxy_secrets_template = """
apiVersion: v1
kind: Secret
metadata:
  name: {{proxy_name}}
data:
  rules.tgz: |
    {{rules_b64 | indent(4)}}
"""

def prepare_waf_rulesets(waf_profile_name):
    # include *.data, REQUEST-90*, RESPONSE-980-CORRELATION
    _, tmp_file_name = tempfile.mkstemp()
    tmp_file_name = tmp_file_name + '.tgz'
    dst_rulesdir = tempfile.mkdtemp()
    src_rulesdir = os.path.join('modsec', 'rules')
    for fname in os.listdir(src_rulesdir):
        if fname.endswith('.data') or fname.startswith('REQUEST-90') or fname.startswith('RESPONSE-980') or fname.startswith('REQUEST-949') or fname.startswith('REQUEST-959'):
            shutil.copy2(os.path.join(src_rulesdir, fname), dst_rulesdir)
    # find the rule file names defined in waf_profile_name
    for rule in models.WafProfileRuleSet.objects(profile_name=waf_profile_name):
        fname = rule.rule_set_name + '.conf'
        shutil.copy2(os.path.join(src_rulesdir, fname), dst_rulesdir)
    with tarfile.open(tmp_file_name, "w:gz") as tar:
        tar.add(dst_rulesdir, arcname="")
    shutil.rmtree(dst_rulesdir)
    return tmp_file_name


def prepare_config_map(app_svc):
    upstream = app_svc.cluster_ip + ":" + str(app_svc.ports[0]['port'])
    nginx_conf = Template(open('modsec/nginx.conf').read()).render(
        cluster_ip_port=upstream, upstream_name=app_svc.name)
    modsec_include = open('modsec/include.conf').read()
    modsec_conf = open('modsec/modsecurity.conf').read()
    crs_setup_conf = open('modsec/crs-setup.conf').read()
    t = Template(proxy_config_template)
    config_name = "proxy-" + app_svc.name
    body = t.render(proxy_name=config_name,
        nginx_conf=nginx_conf, modsec_include=modsec_include,
        modsec_conf=modsec_conf, crs_setup_conf=crs_setup_conf)
    return body


def prepare_secrets(app_svc):
    # prepare waf rule sets
    rules_tar_file = prepare_waf_rulesets(app_svc.proxy_waf_profile)
    rules_b64 = base64.b64encode(open(rules_tar_file, "rb").read()).decode()
    config_name = "proxy-" + app_svc.name
    t = Template(proxy_secrets_template)
    body = t.render(proxy_name=config_name, rules_b64=rules_b64)
    return body


def create_proxy_config(app_svc):
    config_name = "proxy-" + app_svc.name
    body = prepare_config_map(app_svc)
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


def create_proxy_secrets(app_svc):
    config_name = "proxy-" + app_svc.name
    body = prepare_secrets(app_svc)
    body = yaml.safe_load(body)
    v1 = client.CoreV1Api()
    try:
        v1.create_namespaced_secret(body=body, namespace=app_svc.namespace)
    except client.rest.ApiException as e:
        if e.reason == "Conflict":
            v1.patch_namespaced_secret(
                name=config_name, body=body, namespace=app_svc.namespace)
        else:
            raise(e)


def create_proxy_deployment(app_svc):
    # create a pod that reverse proxies to the app_svc
    t = Template(proxy_deployment_template)
    deployment_name = "proxy-" + app_svc.name
    cur_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    body = t.render(proxy_name=deployment_name, date_time="t"+cur_time)
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
    if proxy_svc is None:
        app_svc.proxy_svc_name = ""
        app_svc.proxy_ip = []
        app_svc.proxy_port = 0
    else:
        app_svc.proxy_svc_name = proxy_svc.metadata.name
        if proxy_svc.spec.load_balancer_ip:
            app_svc.proxy_ip = [proxy_svc.spec.load_balancer_ip]
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


def load_kube_config(app_svc):
    kube_profile = models.KubeProfile.objects(name=app_svc.kube_profile).get()
    tmp_fd, tmp_file_name = tempfile.mkstemp(text=True)
    fd = os.fdopen(tmp_fd, "w")
    fd.write(kube_profile.kube_config)
    fd.close()
    config.load_kube_config(tmp_file_name)


def protect_service(app_svc):
    load_kube_config(app_svc)
    create_proxy_config(app_svc)
    create_proxy_secrets(app_svc)
    create_proxy_deployment(app_svc)
    rsp = create_proxy_svc(app_svc)
    update_svc(app_svc, rsp)


def delete_protection(app_svc):
    load_kube_config(app_svc)
    name = "proxy-" + app_svc.name
    namespace = app_svc.namespace
    v1 = client.CoreV1Api()
    v1.delete_namespaced_service(name=name, namespace=namespace)
    v1 = client.AppsV1Api()
    v1.delete_namespaced_deployment(name=name, namespace=namespace)
    update_svc(app_svc, None)


if __name__ == "__main__":
    # svc must not have been deployed or date_modified is greater than date_deployed
    query = {
        "$or": [
            {"$expr": {"$gt": ["$date_modified", "$proxy_date_deployed"]}},
            {"proxy_date_deployed": ""}
        ]
    }
    for svc in models.Service.objects(__raw__=query):
        protect_service(svc)