import os
import time

from flask import Flask, abort, request
from flask_restplus import Api, Resource
from mongoengine import connect

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
        return None


@api.route('/tls-profiles')
class TLSProfileList(Resource):
    def get(self):
        return base_query.get_all_items(models.TLSProfile, **request.args)

    def post(self):
        base_query.create_item(models.TLSProfile, **request.json)


@api.route('/tsl-profile/<string:name>')
class TLSProfile(Resource):
    def get(self, name):
        return base_query.get_item(models.TLSProfile, name=name)

    def put(self, name):
        return base_query.update_item(models.TLSProfile, {'name': name}, **request.json)        

    def delete(self, name):
        base_query.delete_item(models.TLSProfile, name=name)


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