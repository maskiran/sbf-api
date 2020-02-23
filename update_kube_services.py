"""
Add/Update kubernetes services
"""

import datetime
import os
import tempfile

from mongoengine import connect, errors
from kubernetes import config, client

import models


connect(db="sbf")


def create_kube_services_from_kubeconfig(kube_config_file, refresh_time):
    config.load_kube_config(kube_config_file)
    v1 = client.CoreV1Api()
    for svc in v1.list_service_for_all_namespaces().items:
        # if svc.metadata.namespace == "kube-system" or svc.metadata.name == "kubernetes":
        #     continue
        # the keys in the labels cant have dot
        labels = {}
        for key in svc.metadata.labels:
            new_key = key.replace('.', '_')
            labels[new_key] = svc.metadata.labels[key]
        data = {
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
        if db_svc.count() >=1:
            # svc already exists in my system. did anything change? update date_modified
            pass
        else:
            # new doc
            data['date_added'] = datetime.datetime.now()
            data['date_modified'] = datetime.datetime.now()
        data['refresh_time'] = refresh_time
        models.Service.objects(uid=svc.metadata.uid).update(upsert=True, **data)


def main():
    refresh_time = datetime.datetime.now()
    for kube_profile in models.KubeProfile.objects:
        tmp_fd, tmp_file_name = tempfile.mkstemp(text=True)
        fd = os.fdopen(tmp_fd, "w")
        fd.write(kube_profile.kube_config)
        fd.close()
        create_kube_services_from_kubeconfig(tmp_file_name, refresh_time)
    # mark all svcs with refresh time as not current as deleted
    print("Running delete")
    x =models.Service.objects(refresh_time__ne=refresh_time).update(deleted=True)
    print(x)



if __name__ == "__main__":
    main()
