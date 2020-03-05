from mongoengine import Document, StringField, IntField, MapField, DateTimeField, ListField, DictField, BooleanField


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
    Kube and Proxy Service object
    """
    uid = StringField()
    kube_profile = StringField()
    name = StringField(required=True)
    namespace = StringField()
    cluster_ip = StringField()
    ports = ListField()
    labels = ListField()
    creation_timestamp = DateTimeField()
    proxy_port = IntField() # in nodeport deployment this is replaced with host port
    proxy_ip = ListField() # filled in later when the proxy svc is deployed (lbname or nodeport)
    proxy_svc_name = StringField()
    proxy_tls_profile = StringField()
    proxy_waf_profile = StringField()
    proxy_policy_profile = StringField()
    deleted = BooleanField(default=False)
    meta = {
        'indexes': [
            {
                'fields': ['uid'],
                'unique': True
            }
        ]
    }


class PolicyProfile(BaseDocument):
    name = StringField()
    services = ListField(StringField())
    rule_count = IntField()


class PolicyProfileRule(BaseDocument):
    name = StringField()
    profile_name = StringField()
    source = StringField(default="any")
    action = StringField(choices=['allow', 'drop'])
    log = StringField(choices=['log', 'nolog'])


class WafRuleSet(BaseDocument):
    # add ruleset names here (eg. REQUEST-911-PROTOCOL)
    name = StringField(required=True)
    version = StringField()
    meta = {
        'indexes': [
            'version',
            {
                'fields': ['name'],
                'unique': True
            }
        ]
    }


class WafProfile(BaseDocument):
    name = StringField(required=True)
    rule_set_version = StringField()
    rule_count = IntField(default=0)
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
    meta = {
        'indexes': [
            {
                'fields': ['profile_name', 'rule_set_name'],
                'unique': True
            }
        ]
    }


class TlsProfile(BaseDocument):
    name = StringField(required=True)
    certificate = StringField()
    meta = {
        'indexes': [
            {
                'fields': ['name'],
                'unique': True
            }
        ]
    }


class Certificate(BaseDocument):
    name = StringField(required=True)
    body = StringField()
    private_key = StringField()
    subjects = ListField(StringField())
    issue_date = DateTimeField()
    expiry_date = DateTimeField()
    meta = {
        'indexes': [
            {
                'fields': ['name'],
                'unique': True
            }
        ]
    }


class Address(BaseDocument):
    name = StringField(required=True)
    value = StringField(required=True)
    description = StringField()
    meta = {
        'indexes': [
            {
                'fields': ['name'],
                'unique': True
            }
        ]
    }


class KubeProfile(BaseDocument):
    name = StringField(required=True)
    kube_config = StringField()
    cluster = StringField()
    meta = {
        'indexes': [
            {
                'fields': ['name'],
                'unique': True
            }
        ]
    }
