import os
import tempfile
import time

import arrow
from flask import Flask, abort, request
from flask_restplus import Api, Resource
import kubernetes
from mongoengine import connect
import OpenSSL.crypto

import base_query
import models

DB_HOST = os.getenv('MONGODB_HOST', 'mongodb://localhost/sbf')
connect(host=DB_HOST, connect=False)

app = Flask(__name__)
api = Api(app)

@api.route('/services')
class ServiceList(Resource):
    def get(self):
        return base_query.get_all_items(models.Service, **request.args)

    def post(self):
        body = request.json
        return base_query.create_item(models.Service, **body)


@api.route('/service/<string:name>')
class Service(Resource):
    def get(self, name):
        return base_query.get_item(models.Service, name=name)

    def put(self, name):
        data = request.json
        # only proxy*, tls, waf, policy are updateable
        im_fields = ['name', 'namespace', 'cluster_ip', 'ports', 'labels', 'creation_timestamp']
        for im_field in im_fields:
            del data[im_field]
        return base_query.update_item(models.Service, {'name': name}, **request.json)


@api.route('/waf-rule-sets')
class WafRuleSetList(Resource):
    def get(self):
        return base_query.get_all_items(models.WafRuleSet, **request.args)

    def post(self):
        for ruleset in request.json:
            base_query.create_item(models.WafRuleSet, **ruleset)


@api.route('/waf-rule-sets/versions')
class WafRuleSetVersions(Resource):
    def get(self):
        return base_query.distinct_items(models.WafRuleSet)


@api.route('/waf-profiles')
class WafProfileList(Resource):
    def get(self):
        return base_query.get_all_items(models.WafProfile, **request.args)

    def post(self):
        base_query.create_item(models.WafProfile, **request.json)


@api.route('/waf-profile/<string:name>')
class WafProfile(Resource):
    def get(self, name):
        return base_query.get_item(models.WafProfile, name=name)

    def put(self, name):
        data = request.json
        del data['name']
        return base_query.update_item(models.WafProfile, {'name': name}, **data)        

    def delete(self, name):
        base_query.delete_item(models.WafProfile, name=name)
        # delete all the profile rulesets for this profile
        base_query.delete_item(models.WafProfileRuleSet, profile_name=name)
        return


@api.route('/waf-profile-rule-sets/<string:profile_name>')
class WafProfileRuleSetList(Resource):
    def get(self, profile_name):
        return base_query.get_all_items(models.WafProfileRuleSet, profile_name=profile_name, **request.args)

    def post(self, profile_name):
        rule_set_list = request.json['rule_set_list']
        replace = request.json.get('replace', False)
        if replace:
            # delete existing rules on the profile
            base_query.delete_item(models.WafProfileRuleSet, profile_name=profile_name)
        for rule_set_name in rule_set_list:
            data = {'profile_name': profile_name, 'rule_set_name': rule_set_name}
            base_query.create_item(models.WafProfileRuleSet, **data)
        # update waf-profile with the number of rules
        base_query.update_item(models.WafProfile, {'name': profile_name}, rule_count=len(rule_set_list))
        return None


@api.route('/tls-profiles')
class TlsProfileList(Resource):
    def get(self):
        return base_query.get_all_items(models.TlsProfile, **request.args)

    def post(self):
        base_query.create_item(models.TlsProfile, **request.json)


@api.route('/tls-profile/<string:name>')
class TlsProfile(Resource):
    def get(self, name):
        return base_query.get_item(models.TlsProfile, name=name)

    def put(self, name):
        data = request.json
        del data['name']
        return base_query.update_item(models.TlsProfile, {'name': name}, **data)        

    def delete(self, name):
        base_query.delete_item(models.TlsProfile, name=name)


@api.route('/certificates')
class CertificateList(Resource):
    def get(self):
        # rearrange date
        data = base_query.get_all_items(models.Certificate, **request.args)
        for item in data['items']:
            # can't send body and key
            del item['body']
            del item['private_key']
            item['expiry_date'] = item['expiry_date'].get('$date', "")
            item['issue_date'] = item['issue_date'].get('$date', "")
        return data

    def post(self):
        # parse certificate for important information
        cert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, request.json['body'])
        issue_date = arrow.get(cert.get_notBefore().decode(), ['YYYYMMDDHHmmSSz']).datetime
        expiry_date = arrow.get(cert.get_notAfter().decode(), ['YYYYMMDDHHmmSSz']).datetime
        dns = []
        for comp in cert.get_subject().get_components():
            key, value = comp
            if key.decode() == "CN":
                dns.append(value.decode())
        for idx in range(cert.get_extension_count()):
            ext = cert.get_extension(idx)
            if ext.get_short_name().decode() == "subjectAltName":
                dns.extend(ext._subjectAltNameString().split(","))
        base_query.create_item(models.Certificate, exclude_search=["body", "private_key"],
            issue_date=issue_date, expiry_date=expiry_date, subjects=dns, **request.json)


@api.route('/certificate/<string:name>')
class Certificate(Resource):
    def get(self, name):
        return base_query.get_item(models.Certificate, name=name)

    def delete(self, name):
        base_query.delete_item(models.Certificate, name=name)


@api.route('/addresses')
class AddressList(Resource):
    def get(self):
        return base_query.get_all_items(models.Address, **request.args)

    def post(self):
        base_query.create_item(models.Address, **request.json)


@api.route('/address/<string:name>')
class Address(Resource):
    def get(self, name):
        return base_query.get_item(models.Address, name=name)

    def put(self, name):
        data = request.json
        del data['name']
        return base_query.update_item(models.Address, {'name': name}, **data)        

    def delete(self, name):
        base_query.delete_item(models.Address, name=name)


@api.route('/kube-profiles')
class KubeProfileList(Resource):
    def get(self):
        data = base_query.get_all_items(models.KubeProfile, **request.args)
        # delete kube_config
        for item in data['items']:
            item['kube_config'] = 'CONTENTS-HIDDEN'
        return data

    def post(self):
        # get the clusters in the kube_config
        kube_config = request.json['kube_config']
        tmp_fd, tmp_file_name = tempfile.mkstemp(text=True)
        fd = os.fdopen(tmp_fd, "w")
        fd.write(kube_config)
        fd.close()
        kubernetes.config.load_kube_config(tmp_file_name)
        _, cur_context = kubernetes.config.list_kube_config_contexts()
        base_query.create_item(models.KubeProfile,
            cluster=cur_context['name'], exclude_search=["kube_config"],
            **request.json)


@api.route('/kube-profile/<string:name>')
class KubeProfile(Resource):
    def get(self, name):
        item = base_query.get_item(models.KubeProfile, name=name)
        # dont send kube config
        item['kube_config'] = "CONTENTS-HIDDEN"
        return item

    def put(self, name):
        data = request.json
        if data['kube_config'] == 'CONTENTS-HIDDEN':
            # dont update kube_config
            del data['kube_config']
        del data['name']
        return base_query.update_item(models.KubeProfile, {'name': name},
            exclude_search=["kube_config"], **data)        

    def delete(self, name):
        base_query.delete_item(models.KubeProfile, name=name)


@api.route('/policy-profiles')
class PolicyProfileList(Resource):
    def get(self):
        """
        Get rules for the given service name
        """
        return base_query.get_all_items(models.PolicyProfile, **request.args)

    def post(self):
        body = request.json
        return base_query.create_item(models.PolicyProfile, **body)


@api.route('/policy-profile/<string:name>')
class PolicyProfile(Resource):
    def get(self, name):
        return base_query.get_item(models.PolicyProfile, name=name)

    def delete(self, name):
        return base_query.delete_item(models.PolicyProfile, name=name)


@api.route('/policy-rules/<string:policy_profile_name>')
class PolicyProfileRuleList(Resource):
    def get(self, policy_profile_name):
        return base_query.get_all_items(models.PolicyProfileRule,
            profile_name=policy_profile_name, **request.args)

    def post(self, policy_profile_name):
        body = request.json
        body['profile_name'] = policy_profile_name
        base_query.create_item(models.PolicyProfileRule, **body)
        # get number of rules in the profile
        items = base_query.get_all_items(models.PolicyProfileRule, profile_name=policy_profile_name)
        base_query.update_item(models.PolicyProfile, {'name': policy_profile_name}, rule_count=items['count'])


@api.route('/policy-rule/<string:policy_profile_name>/<string:rule_id>')
class PolicyProfileRule(Resource):
    def get(self, policy_profile_name, rule_id):
        return base_query.get_item(models.PolicyProfileRule,
            profile_name=policy_profile_name, id=rule_id)

    def put(self, policy_profile_name, rule_id):
        body = request.json
        del body['id']
        return base_query.update_item(models.PolicyProfileRule,
            {'profile_name': policy_profile_name, 'id': rule_id},
            body)

    def delete(self, policy_profile_name, rule_id):
        return base_query.delete_item(models.PolicyProfileRule,
            profile_name=policy_profile_name, id=rule_id)


if __name__ == "__main__":
    app.run(debug=True)