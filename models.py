from mongoengine import Document, StringField, IntField, MapField, DateTimeField


class BaseDocument(Document):
    date_added = DateTimeField()
    date_modified = DateTimeField()
    search = StringField()
    # enable text search on 'search' field
    meta = {
        'indexes': [
            "$search"
        ],
        'abstract': True
    }


class Service(BaseDocument):
    """
    Service object
    """
    name = StringField(required=True, unique=True)
    description = StringField(default="")
    listen_port = IntField(required=True)
    target = StringField(required=True)
    end_point = StringField()
    tls_profile = StringField()
    waf_profile = StringField()
    meta = {
        'indexes': [
            {
                'fields': ['name'],
                'unique': True
            }
        ]
    }


class Rule(BaseDocument):
    name = StringField()
    service_name = StringField()
    source = StringField(default="any")
    action = StringField(choices=['allow', 'drop'])
    log = StringField(choices=['log', 'nolog'])


class WafRuleSet(BaseDocument):
    # add ruleset names here (eg. REQUEST-911-PROTOCOL)
    name = StringField()
    version = StringField()
    meta = {
        'indexes': ['version']
    }


class WafProfile(BaseDocument):
    name = StringField()
    rule_set_version = StringField()
    meta = {
        'indexes': [
            {
                'fields': ['name'],
                'unique': True
            }
        ]
    }


class WafProfileRuleSet(BaseDocument):
    profile_name = StringField()
    rule_set_name = StringField()


class TLSProfile(BaseDocument):
    name = StringField()
    meta = {
        'indexes': [
            {
                'fields': ['name'],
                'unique': True
            }
        ]
    }