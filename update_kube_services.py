"""
Add/Update kubernetes services
"""

import datetime
from multiprocessing import Process
import os
import tempfile

from mongoengine import connect, errors, disconnect
from kubernetes import config, client, watch

import create_proxy_svc
import models


MONGODB = "mongodb://localhost/sbf"


def upsert_service(kube_profile_name, svc, modified=False):
    # svc is the data obtained from the list_service or watch event
    # that has metadata and spec dicts
    labels = []
    svc_labels = svc.metadata.labels
    if svc_labels is None:
        svc_labels = {}
    for (key, value) in svc_labels.items():
        labels.append({
            'name': key,
            'value': value
        })
    data = {
        "kube_profile": kube_profile_name,
        "labels": labels,
        "creation_timestamp": svc.metadata.creation_timestamp,
        "name": svc.metadata.name,
        "namespace": svc.metadata.namespace,
        "uid": svc.metadata.uid,
        "cluster_ip": svc.spec.cluster_ip,
        "ports": list(map(lambda x: {'name': x.name, 'port': x.port},
                          svc.spec.ports)),
    }
    db_svc = models.Service.objects(uid=svc.metadata.uid)
    if db_svc.count() < 1:
        # new doc
        data['date_added'] = datetime.datetime.now()
        data['date_modified'] = datetime.datetime.now()
    if modified:
        data['date_modified'] = datetime.datetime.now()

    rsp = models.Service.objects(uid=svc.metadata.uid).modify(
        upsert=True, new=True, **data)
    create_proxy_svc.protect_service(rsp)


def delete_service(event_object):
    app_svc = models.Service.objects(uid=event_object.metadata.uid).get()
    create_proxy_svc.delete_protection(app_svc)
    models.Service.objects(uid=event_object.metadata.uid).delete()


def process_event(event_type, event_object, kube_profile_name):
    if event_object.metadata.namespace == "kube-system" or event_object.metadata.name == "kubernetes":
        return
    # if event has labels "type=sbf-proxy"
    ltype = event_object.metadata.labels.get('type', "")
    if ltype == "sbf-proxy":
        return
    if event_type == "ADDED":
        upsert_service(kube_profile_name, event_object)
    elif event_type == "MODIFIED":
        upsert_service(kube_profile_name, event_object, modified=True)
    elif event_type == "DELETED":
        delete_service(event_object)


def monitor_kube(kube_profile):
    connect(host=MONGODB)

    tmp_fd, tmp_file_name = tempfile.mkstemp(text=True)
    fd = os.fdopen(tmp_fd, "w")
    fd.write(kube_profile.kube_config)
    fd.close()
    config.load_kube_config(tmp_file_name)
    v1 = client.CoreV1Api()
    # do a first consolidation of all the services
    rsp = v1.list_service_for_all_namespaces()
    resource_version = rsp.metadata.resource_version
    for svc in rsp.items:
        process_event('ADDED', svc, kube_profile.name)
    watcher = watch.Watch()
    for event in watcher.stream(v1.list_service_for_all_namespaces, resource_version=resource_version):
        process_event(event['type'], event['object'], kube_profile.name)


def main():
    process_ids = []
    connect(host=MONGODB)
    kube_profiles = list(models.KubeProfile.objects)
    disconnect()
    for kube_profile in kube_profiles:
        pd = Process(target=monitor_kube, args=(kube_profile,))
        pd.start()
        process_ids.append(pd)
    for pd in process_ids:
        pd.join()


if __name__ == "__main__":
    main()
