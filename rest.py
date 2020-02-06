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
        return base_query.get_all(models.Service, **request.args)

    def post(self):
        body = request.json
        return base_query.create_item(models.Service, body)


@api.route('/service/<string:name>')
class Service(Resource):
    def get(self, name):
        return base_query.get(models.Service, name=name)


@api.route('/rules')
class RuleList(Resource):
    def get(self):
        return base_query.get_all(models.Rule, **request.args)

    def post(self):
        body = request.json
        return base_query.create_item(models.Rule, body)



if __name__ == "__main__":
    app.run(debug=True)