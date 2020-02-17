"""
This file sets up the yaml and gets resource information about the account.

Tis is a pile of hot garbage. I want to collate entry, vars, and runner into
sane python scripts.

"""
import os
import logging
from troposphere import Template, Parameter
import boto3
import yaml
from ecs_cluster_deployer.runner import Runner

logger = logging.getLogger()
logging.basicConfig()
logger.setLevel(logging.INFO)

class ECSVars(Runner):
    """ This class sets up the yaml file ingress and calls the runner """
    def __init__(self):
        # self.account = self._get_account()
        self.region = os.environ.get('AWS_DEFAULT_REGION')
        self.ami = os.environ.get('AMI')
        self.ecs_cluster_deployer_version = os.environ.get('ECS_CLUSTER_DEPLOYER_VERSION')
        self.s3_bucket = os.environ.get(
            'S3_BUCKET',
            'ecs-cluster-deployer-{}-{}'.format(self.account, self.region)
        )
        self.values_file = os.environ.get(
            'VALUES_FILE',
            'infra.yml'
        )
        super(ECSVars, self).__init__()

        # User defined values
        self.base = self.open_vars_file()

        # try to gether information about the vpc / subnet
        self.ec2 = boto3.client('ec2', region_name=self.region)
        self.get_vpc_info()
        self.get_subnet_info()

        # init of the cloudformation
        self.template = Template()
        self.template.add_version("2010-09-09")
        self.add_default_parameters()

    def open_vars_file(self):
        """ Load the users infra.yml """
        with open(self.values_file, 'r') as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                logger.info(exc)

    def get_vpc_info(self):
        """ If you dont have a vpc set, it iwll look for default """
        if not self.base['cluster'].get('vpc'):
            res = self.ec2.describe_vpcs()
            self.base['cluster']['vpc'] = [vpc['VpcId'] for vpc in res['Vpcs'] if vpc['IsDefault']][0]
            logger.info('No vpc selected, using default vpc')
            logger.info(self.base['cluster']['vpc'])

    def get_subnet_info(self):
        """ If the subnets aren't set this will try and gather them """
        if not self.base['cluster'].get('subnets'):
            res = self.ec2.describe_subnets()
            self.base['cluster']['subnets'] = [subnet['SubnetId'] for subnet in res['Subnets'] if subnet['VpcId'] == self.base['cluster']['vpc']]
            self.base['cluster']['availability_zones'] = [subnet['AvailabilityZone'] for subnet in res['Subnets'] if subnet['VpcId'] == self.base['cluster']['vpc']]
            logger.info('No subnets selected, using defaults')
            logger.info(self.base['cluster']['subnets'])
            logger.info('Inferring AZs')
            logger.info(self.base['cluster']['availability_zones'])

    def get_efs_info(self):
        '''
        Make sure we can do something about our efs mounts
        If we have an id, use the id or add security group to itself.
        Otherwise, create and do the security group stuff:
            - create a rule on the default vpc that allows ingress from cluster badge
        '''

    # def to_dict(self):
    #     """ Con """
    #     pprint(self.template.to_dict())

    def deploy(self):
        """ Deploy the cloudformation """
        self.push_cloudformation(self.template)

    @property
    def version(self):
        return os.environ.get('VERSION')

    @property
    def account(self):
        """ Discover the account """
        sts = boto3.client('sts')
        res = sts.get_caller_identity()
        return res['Account']

    def add_default_parameters(self):
        """ Adds default parameters to the stack """
        logger.info('Adding default parameters...')
        self.template.add_parameter(
            Parameter(
                "S3Bucket",
                Type="String",
                Default=f"kloudcover-public-{self.region}-{self.account}"
            )
        )
        self.template.add_parameter(
            Parameter(
                "S3Prefix",
                Type="String",
                Default=f"ecs_cluster_deployer/{self.ecs_cluster_deployer_version}"
            )
        )
        self.template.add_parameter(
            Parameter(
                "Version",
                Type="String",
                Default=self.version
            )
        )
        self.template.add_parameter(
            Parameter(
                "ClusterName",
                Type="String",
                Default=self.base['cluster']['name']
            )
        )
