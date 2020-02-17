""" Constructs the compute for the cluster using troposphere """
import json
import os
import logging
import urllib.request as urllib2
from dateutil import parser


from troposphere import (
    Parameter,
    Ref,
    Template,
    Sub,
    GetAtt,
    Output,
    Export,
    Base64,
    Join,
    ImportValue,
    Equals,
    If
)
from troposphere.iam import Role, InstanceProfile, Policy
from troposphere.awslambda import Function, Code
from troposphere.autoscaling import AutoScalingGroup, LaunchConfiguration
from troposphere.sns import Topic
from troposphere.ec2 import (
    SecurityGroup,
    SpotFleetRequestConfigData,
    SecurityGroupRule,
    Monitoring,
    SpotFleet,
    SecurityGroups,
    SecurityGroupIngress,
    BlockDeviceMapping,
    EBSBlockDevice,
    LaunchSpecifications,
    SpotFleetTagSpecification,
    IamInstanceProfile,
    Tag
)
from troposphere.stepfunctions import StateMachine
from troposphere.cloudwatch import Alarm, MetricDimension
from troposphere.applicationautoscaling import (
    ScalingPolicy,
    StepAdjustment,
    ScalableTarget,
    TargetTrackingScalingPolicyConfiguration,
    StepScalingPolicyConfiguration
)
import botocore
import boto3
from jinja2 import Template as J2Template #pylint: disable=E0401

from ecs_cluster_deployer.compute.lambda_scaler import add_scaling
from ecs_cluster_deployer.utils import sanitize_cfn_resource_name
from ecs_cluster_deployer.iam.instance_profile import add_instance_profile_to_template

logger = logging.getLogger()
logging.basicConfig()
logger.setLevel(logging.INFO)

class EC2Instances: #pylint: disable=R0902
    """ Creates spot fleets and ASGs for the ECS Cluster """
    def __init__(self, ecs_obj):
        self.ec2 = boto3.client('ec2', region_name=ecs_obj.region)
        self.ssm = boto3.client('ssm', region_name=ecs_obj.region)
        self.region = ecs_obj.region
        self.template = ecs_obj.template
        self.version = ecs_obj.version
        self.ecs_deployer_version = os.environ.get('ECS_CLUSTER_DEPLOYER_VERSION')
        self.instance_base = ecs_obj.base['ec2_instances']
        self.asgs = ecs_obj.base['ec2_instances'].get('auto_scaling_groups', [])
        self.spot_fleets = ecs_obj.base['ec2_instances'].get('spot_fleets', [])
        self.cluster = ecs_obj.base['cluster']
        self.instance_role = self.add_instance_profile()
        ecs_obj.stack_name = "{}-asg-{}".format(self.cluster['name'], self.version)
        # do stuff
        self.get_parameters()
        self.add_base_resources()

        for fleet in self.spot_fleets:
            self.add_spot_fleet(fleet)

        for asg in self.asgs:
            self.add_auto_scaling_group(asg)

    @property
    def keypair(self):
        """ If theres not a keypair, create one """
        # breakpoint()
        if not self.cluster.get('keypair'):
            try:
                self.ssm.get_parameter(
                    Name='/ecs-maestro/{}/keypair'.format(self.cluster['name'])

                )
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'ParameterNotFound':
                    self.create_key()
                else:
                    raise
            return 'ecs-maestro-{}'.format(self.cluster['name'])
        return self.cluster['keypair']

    def create_key(self):
        """ This creates a keypair in ec2 and puts it in SSM """
        res = self.ec2.create_key_pair(
            KeyName='ecs-maestro-{}'.format(self.cluster['name'])
        )
        self.ssm.put_parameter(
            Name='/ecs-maestro/{}/keypair'.format(self.cluster['name']),
            Value=res['KeyMaterial'],
            Description="ClusterMaestro ssh key for {}".format(self.cluster['name']),
            Type='SecureString'
        )
        logger.info('Created KeyPair for ssm')

    @property
    def ami(self):
        """
        Gets the default ami for ecs

        not sure if I need this since I'm using packer

        """
        return os.environ.get('AMI')

    #     if os.environ.get('AMI', self.cluster.get('ami')):
    #         self.ami = os.environ.get('AMI', self.cluster.get('ami'))
    #     else:
    #         # get the latest ecs AMI
    #         res = self.ec2.describe_images(Owners=['amazon'], Filters=[{
    #             'Name': 'name',
    #             'Values': ['amzn-ami-*-amazon-ecs-optimized']
    #         }])
    #         self.ami = self.newest_image(res['Images'])['ImageId']
    #
    # def newest_image(self, list_of_images):
    #     latest = None
    #     for image in list_of_images:
    #         if not latest:
    #             latest = image
    #             continue
    #
    #         if parser.parse(image['CreationDate']) > parser.parse(latest['CreationDate']):
    #             latest = image
    #     return latest['ImageId']

    def get_parameters(self):
        """ Get the parameters for the Stack  """
        self.template.add_parameter(
            Parameter(
                "Status",
                Type="String",
                Default="active"
            )
        )
        self.template.add_parameter(
            Parameter(
                "ScaleOutAdustment",
                Type="String",
                Default="2"
            )
        )
        self.template.add_parameter(
            Parameter(
                "ScaleInAdjustment",
                Type="String",
                Default="1"
            )
        )


        if self.asgs:
            asg = self.asgs[0]
            desired_instances = asg.get('desired_instances', 1)
            self.template.add_parameter(
                Parameter(
                    "ASGCapacity",
                    Type="String",
                    Default=str(desired_instances)
                )
            )
            self.template.add_parameter(
                Parameter(
                    "ASGMaxSize",
                    Type="String",
                    Default=str(asg.get('max_instances', desired_instances))
                )
            )
            self.template.add_parameter(
                Parameter(
                    "ASGMinSize",
                    Type="String",
                    Default=str(asg.get('min_instances', desired_instances))
                )
            )
        if self.spot_fleets:
            spot_fleet = self.spot_fleets[0]
            desired_weight = spot_fleet.get('desired_weight', 1)
            self.template.add_parameter(
                Parameter(
                    "SpotWeight",
                    Type="String",
                    Default=str(desired_weight)
                )
            )
            self.template.add_parameter(
                Parameter(
                    "SpotMaxWeight",
                    Type="String",
                    Default=str(spot_fleet.get('max_weight', desired_weight))
                )
            )
            self.template.add_parameter(
                Parameter(
                    "SpotMinWeight",
                    Type="String",
                    Default=str(spot_fleet.get('min_weight', desired_weight))
                )
            )
            self.template.add_parameter(
                Parameter(
                    "SpotTaskThresholdOut",
                    Type="String",
                    Default=str(spot_fleet.get('task_threshold_out', "3")),
                    Description="If the schedulable tasks is below this number scale the ec2 spot cluster out"
                )
            )
            self.template.add_parameter(
                Parameter(
                    "SpotTaskThresholdIn",
                    Type="String",
                    Default=str(spot_fleet.get('task_threshold_in', "10")),
                    Description="If the schedulable tasks is above this number scale the ec2 spot cluster in"
                )
            )

    def add_base_resources(self):
        """ Allow ingress from load balancers with this """
        ingress_sg = SecurityGroup(
            "IncomingSg",
            GroupDescription="SG for ecs instances for incoming alb",
            VpcId=self.cluster.get('vpc'),
            SecurityGroupIngress=[
                SecurityGroupRule(
                    IpProtocol="tcp",
                    FromPort=0,
                    ToPort=64500,
                    SourceSecurityGroupId=ImportValue(f"{self.cluster['name']}-cluster:ALBBadgeSg")
                )
            ]
        )
        self.template.add_resource(ingress_sg)

    def open_userdata(self):
        """ Set userdata file for instances """
        efs_mounts = []
        if self.instance_base.get('efs_mounts'):
            for mount in self.instance_base.get('efs_mounts'):
                efs_mounts.append({
                    "path": mount.get('local_path'),
                    "id": mount.get('efs_id')
                })
        text = open(self.instance_base.get('user_data', '/ecs_cluster_deployer/compute/ecs_user_data.j2'), "r").read()
        t = J2Template(text)
        return t.render(
            cluster=self.cluster.get('name'),
            efs_mounts=efs_mounts,
            ecs_timeout=self.spot_fleets[0].get('timeout', "2m"),
            ecs_deployer_version=self.ecs_deployer_version,
            version=self.version
        )

    @property
    def block_devices(self):
        """ Get block devices for the EC2 instances """
        block_devices = []
        for block in self.instance_base.get('ebs_mounts'):
            block_devices.append(BlockDeviceMapping(
                DeviceName=block.get('device_name'),
                Ebs=EBSBlockDevice(
                    VolumeSize=block.get('size', 8),
                    DeleteOnTermination=True,
                    VolumeType='gp2'
                )
            ))

        return block_devices

    def add_auto_scaling_group(self, asg):
        """ Add auto scaling group to stack """
        default_security_groups = [
            SecurityGroups(GroupId=Ref('IncomingSg')),
            SecurityGroups(GroupId=ImportValue('{}-cluster:DBBadgeSg'.format(self.cluster.get('name')))),
        ]
        for group in self.cluster.get('security_groups', []):
            default_security_groups.append(
                SecurityGroups(GroupId=group)
            )

        launch_config = LaunchConfiguration(
            "ASGLaunchConfig{}".format(sanitize_cfn_resource_name(asg.get('name'))),
            IamInstanceProfile=self.instance_role,
            ImageId=self.ami,
            InstanceType=asg.get('instance_type'),
            KeyName=self.keypair,
            SecurityGroups=default_security_groups,
            BlockDeviceMappings=self.block_devices,
            UserData=Base64(Sub(self.open_userdata()))
        )
        # launch config
        self.template.add_resource(launch_config)
        self.template.add_condition('IsActive', Equals(Ref('Status'), 'active'))

        auto_scaling_group = AutoScalingGroup(
            "ASG{}".format(sanitize_cfn_resource_name(asg.get('name'))),
            VPCZoneIdentifier=self.cluster.get('subnets'),
            Cooldown=300,
            DesiredCapacity=asg.get('desired_instances', 1),
            HealthCheckType='EC2',
            HealthCheckGracePeriod=60,
            LaunchConfigurationName=Ref(launch_config),
            MinSize=If('IsActive', asg.get('min_size', 1), 0),
            MaxSize=asg.get('max_size', 1)
        )
        self.template.add_resource(auto_scaling_group)

    def add_instance_profile(self):
        '''
        return arn - or getatt arn
        '''
        if self.instance_base.get('instance_profile_arn'):
            return Sub(self.instance_base.get('instance_profile_arn'))
        return add_instance_profile_to_template(self.template)


    def add_spot_fleet(self, spot_fleet):
        """ Add spot fleet to stack """
        self.open_userdata()

        launch_specs = []
        default_security_groups = [
            SecurityGroups(GroupId=Ref('IncomingSg')),
            SecurityGroups(GroupId=ImportValue('{}-cluster:DBBadgeSg'.format(self.cluster.get('name')))),
        ]
        for group in self.cluster.get('security_groups', []):
            default_security_groups.append(
                SecurityGroups(GroupId=group)
            )

        for bid in spot_fleet['bids']:

            launch_specs.append(
                LaunchSpecifications(
                    BlockDeviceMappings=self.block_devices,
                    IamInstanceProfile=IamInstanceProfile(Arn=self.instance_role),
                    ImageId=self.ami,
                    InstanceType=bid.get('instance_type'),
                    KeyName=self.keypair,
                    SecurityGroups=default_security_groups,
                    SubnetId=Join(",", self.cluster.get('subnets')),
                    SpotPrice=str(bid.get('price')),
                    UserData=Base64(Sub(self.open_userdata())),
                    Monitoring=Monitoring(Enabled=True),
                    WeightedCapacity=bid.get('weight', 1),
                    TagSpecifications=[SpotFleetTagSpecification(
                        ResourceType='instance',
                        Tags=[
                            Tag("cluster", self.cluster.get('name')),
                            Tag("Name", self.cluster.get('name'))
                        ]
                    )]
                )
            )

        spot_fleet_role = Role(
            "SpotFleetRole",
            AssumeRolePolicyDocument={
                "Statement": [{
                    "Effect": "Allow",
                    "Action": "sts:AssumeRole",
                    "Principal": {"Service": "spotfleet.amazonaws.com"},
                }]
            },
            Policies=[
                Policy(
                    PolicyName="ec2-spot-fleet",
                    PolicyDocument={
                        "Statement": [{
                            "Effect": "Allow",
                            "Action": [
                                "ec2:Describe*",
                                "ec2:CancelSpotFleetRequests",
                                "ec2:CancelSpotInstanceRequests",
                                "ec2:ModifySpotFleetRequest",
                                "ec2:RequestSpotFleet",
                                "ec2:RequestSpotInstances",
                                "ec2:TerminateInstances",
                                "ec2:CreateTags",
                                "iam:PassRole",
                                "iam:ListRoles",
                                "iam:ListInstanceProfiles"
                            ],
                            "Resource": "*"
                        }]
                    }
                )
            ]
        )
        self.template.add_resource(spot_fleet_role)

        spot_resource = SpotFleet(
            "SpotFleet{}".format(sanitize_cfn_resource_name(spot_fleet.get('name'))),
            SpotFleetRequestConfigData=SpotFleetRequestConfigData(
                AllocationStrategy="diversified",
                IamFleetRole=GetAtt("SpotFleetRole", "Arn"),
                LaunchSpecifications=launch_specs,
                TargetCapacity=spot_fleet.get('desired_weight')
            )
        )

        self.template.add_resource(spot_resource)
        if self.instance_base.get('autoscaling'):
            add_scaling(spot_fleet, self.template, self.cluster.get('name'))


    def get_cloudformation(self):
        """ get template """
        return self.template.to_json()
