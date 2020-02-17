""" Cluster validation """
import logging
import yaml
from cerberus import Validator, SchemaError #pylint: disable=E0401

logger = logging.getLogger()
logging.basicConfig()
logger.setLevel(logging.INFO)

cluster = """
cluster:
  type: dict
  schema:
    name:
      type: string
      required: true
    vpc:
      type: string
      regex: (vpc)+-[0-9a-fA-F]+
      required: true
    ami:
      type: string
      regex: (ami)+-[0-9a-fA-F]+
    keypair:
      type: string
    availability_zones:
      type: list
      schema:
        type: string
        regex: ^[a-zA-Z]+-[a-zA-Z]+-[0-9a-z]+(?:,[a-zA-Z]+-[a-zA-Z]+-[0-9a-z]+)+$
        minlength: 8
    subnets:
      type: list
      schema:
        type: string
        regex: (subnet)+-[0-9a-fA-F]+
        minlength: 15
    security_groups:
      type: list
      schema:
        type: string
        regex: (sg)+-[0-9a-fA-F]+
        minlength: 11
    security_group_ingress:
      type: list
      schema:
        type: string
        regex: (sg)+-[0-9a-fA-F]+
        minlength: 11

"""
def validate_cluster(cluster_obj):
    """ Validate cluster schema """
    v = Validator()
    cluster_schema = yaml.load(cluster)
    if not v.validate(cluster_obj, cluster_schema):
        logger.info(cluster_obj)
        raise SchemaError(v.errors)
    # yaml.load(cluster)
    # v = validate()

def validate_ec2(ec2_obj):
    pass
