""" ECS Cluster Troposphere """
import json
import boto3

from troposphere import Parameter, Ref, Sub, GetAtt, Output, Export
from troposphere.iam import Role, InstanceProfile, Policy
from troposphere.awslambda import Function, Code, Environment, Permission
from troposphere.ecs import Cluster, TaskDefinition, ContainerDefinition, LogConfiguration
from troposphere.ec2 import SecurityGroup
from troposphere.logs import LogGroup
from troposphere.events import Target, Rule
from troposphere.stepfunctions import StateMachine
from troposphere.ecs import Environment as ECSEnvironment
from ecs_cluster_deployer.cluster.asg_cleanup import add_asg_cleanup
from ecs_cluster_deployer.utils import sanitize_cfn_resource_name

class ECSCluster: #pylint: disable=R0903
    """  Build cluster cloudformation """
    def __init__(self, ecs_obj):
        self.region = ecs_obj.region
        self.ecs_obj = ecs_obj
        self.cluster_vars = ecs_obj.base['cluster']
        self.t = self.ecs_obj.template
        self.version = ecs_obj.version
        self.scaffold()
        ecs_obj.stack_name = "{}-cluster".format(ecs_obj.base['cluster']['name'])

    def scaffold(self):
        """ Create long lived stack resources for the cluster """
        self.t.add_resource(Cluster(
            "Cluster",
            ClusterName=self.cluster_vars['name']
        ))
        OUTPUT_SG = ["ALB", "DB", "Cache", "Aux"]
        for sg in OUTPUT_SG:
            tmpsg = SecurityGroup(
                "{}BadgeSg".format(sg),
                GroupDescription="SG for {} to wear in order to talk to ecs instances".format(sg),
                VpcId=self.cluster_vars.get('vpc')
            )
            self.t.add_resource(tmpsg)
            self.t.add_output(
                Output(
                    "{}BadgeSg".format(sg),
                    Description="{} Security Group Badge".format(sg),
                    Export=Export(Sub("${AWS::StackName}:%sBadgeSg" % sg)),
                    Value=GetAtt(tmpsg, "GroupId")
                )
            )
        # Refactor like this
        ### removing this because it's in the agent now
        add_asg_cleanup(self.t, sanitize_cfn_resource_name(self.cluster_vars['name']))

        # add metric lambda
        self.t.add_resource(Function(
            "ECSMetricLambda",
            Code=Code(
                S3Bucket=Sub("${S3Bucket}"),
                S3Key=Sub("${S3Prefix}/deployment.zip")
            ),
            Handler="metrics.cluster_metrics.lambda_handler",
            Role=GetAtt("CronLambdaRole", "Arn"),
            Runtime="python3.7",
            MemorySize=128,
            Timeout=300,
            Environment=Environment(
                Variables={
                    "CLUSTER": Sub("${ClusterName}"),
                    "ASGPREFIX": Sub("${ClusterName}-asg-"),
                    "REGION": Ref("AWS::Region")
                }

            )
        ))

        self.t.add_resource(Role(
            "CronLambdaRole",
            AssumeRolePolicyDocument={
                "Statement": [{
                    "Effect": "Allow",
                    "Action": "sts:AssumeRole",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                }]
            },
            Policies=[
                Policy(
                    PolicyName="logs-and-stuff",
                    PolicyDocument={
                        "Statement": [{
                            "Effect": "Allow",
                            "Action": [
                                "logs:*"
                            ],
                            "Resource": "arn:aws:logs:*:*:*"
                        }, {
                            "Effect": "Allow",
                            "Action": [
                                "ec2:DescribeAutoScalingGroups",
                                "ec2:UpdateAutoScalingGroup",
                                "ecs:*",
                                "cloudwatch:PutMetricData"
                            ],
                            "Resource": "*"
                        }]
                    }
                )
            ]
        ))
        # run metrics every minute
        self.t.add_resource(Rule(
            "CronStats",
            ScheduleExpression="rate(1 minute)",
            Description="Cron for cluster stats",
            Targets=[
                Target(
                    Id="1",
                    Arn=GetAtt("ECSMetricLambda", "Arn"))
            ]
        ))
        self.t.add_resource(Permission(
            "StatPerm",
            Action="lambda:InvokeFunction",
            FunctionName=GetAtt("ECSMetricLambda", "Arn"),
            Principal="events.amazonaws.com",
            SourceArn=GetAtt("CronStats", "Arn")
        ))
