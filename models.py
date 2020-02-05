from mongoengine import Document, StringField, IntField, MapField, DateTimeField
    

class Service(Document):
    """
    Service object
    """
    name = StringField(required=True, unique=True)
    description = StringField(default="")
    fqdn = StringField()
    listen_port = IntField(required=True)
    tls_profile = StringField()
    target = StringField(required=True)
    waf_profile = StringField()


class Rule(Document):
    name = StringField()
    service_id = StringField()
    service_name = StringField()
    source = StringField(default="any")
    action = StringField(choices=['ALLOW', 'DROP'])

        