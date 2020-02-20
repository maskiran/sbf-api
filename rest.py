import os
import time

import arrow
from flask import Flask, abort, request
from flask_restplus import Api, Resource
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
        del data['name']
        return base_query.update_item(models.Service, {'name': name}, **request.json)

    def delete(self, name):
        # delete service policy
        base_query.delete_item(models.Rule, service_name=name)
        return base_query.delete_item(models.Service, name=name)


@api.route('/service/<string:name>/rules')
class RuleList(Resource):
    def get(self, name):
        """
        Get rules for the given service name
        """
        return base_query.get_all_items(models.Rule, service_name=name, **request.args)

    def post(self, name):
        body = request.json
        return base_query.create_item(models.Rule, service_name=name, **body)


@api.route('/service/<string:name>/rule/<string:rule_id>')
class Rule(Resource):
    def put(self, name, rule_id):
        return base_query.update_item(models.Rule, {'id': rule_id}, **request.json)        

    def delete(self, name, rule_id):
        return base_query.delete_item(models.Rule, id=rule_id)


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
        return base_query.update_item(models.WafProfile, {'name': name}, **request.json)        

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
class TLSProfileList(Resource):
    def get(self):
        return base_query.get_all_items(models.TLSProfile, **request.args)

    def post(self):
        base_query.create_item(models.TLSProfile, **request.json)


@api.route('/tls-profile/<string:name>')
class TLSProfile(Resource):
    def get(self, name):
        return base_query.get_item(models.TLSProfile, name=name)

    def put(self, name):
        return base_query.update_item(models.TLSProfile, {'name': name}, **request.json)        

    def delete(self, name):
        base_query.delete_item(models.TLSProfile, name=name)


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

    def put(self, name):
        return base_query.update_item(models.Certificate, {'name': name}, **request.json)        

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
        return base_query.update_item(models.Address, {'name': name}, **request.json)        

    def delete(self, name):
        base_query.delete_item(models.Address, name=name)


if __name__ == "__main__":
    app.run(debug=True)