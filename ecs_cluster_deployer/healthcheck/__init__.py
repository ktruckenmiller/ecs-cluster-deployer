"""
This library creates a task, checks it's health, and cleans up failed states
"""
import time
import logging
from pprint import pprint
from troposphere import (
    Parameter,
    Ref,
    Template,
    Sub,
    GetAtt,
    Output,
    Export,
    Join,
    ImportValue
)
from troposphere.ecs import (
    TaskDefinition,
    ContainerDefinition
)
import boto3
import botocore

logger = logging.getLogger()
logging.basicConfig()
logger.setLevel(logging.INFO)

class HealthCheck:
    """
    This class can set up new tasks, checks their health, and then sets
    cloudformation stacks as inactive or active based on if that task ran
    """
    def __init__(self, ecs_obj):
        self.ecs = boto3.client('ecs')
        self.cf = boto3.client('cloudformation')
        self.t = Template()
        self.t.add_parameter(Parameter(
            "Version",
            Type="String"
        ))
        self.region = ecs_obj.region
        self.ecs_obj = ecs_obj
        self.cluster_vars = ecs_obj.base['cluster']
        self.version = ecs_obj.version
        self.cluster_name = ecs_obj.base['cluster']['name']
        ecs_obj.stack_name = "{}-cluster-health-task".format(self.cluster_name)

    def deploy(self):
        """ Deploy an ECS task """
        self.create_task()
        self.ecs_obj.template = self.t
        self.ecs_obj.deploy()

    def deactivate_old(self):
        """ Deactive cloudformation stack by setting it as inactive """
        logger.info('Cluster fleet updated, inactivating old stacks...')
        stacks = self.get_old_stacks()
        for stack in stacks:
            logger.info("Inactivating")
            logger.info(stack)
            try:
                self.cf.update_stack(
                    StackName=stack,
                    Parameters=[{
                        'ParameterKey': 'Status',
                        'ParameterValue': 'inactive'
                    }],
                    UsePreviousTemplate=True,
                    Capabilities=['CAPABILITY_IAM']
                )
            except botocore.exceptions.ClientError as e:
                logger.error(e)

    def get_old_stacks(self):
        """ get old stacks in cluster """
        pager = self.cf.get_paginator("list_stacks")
        iterator = pager.paginate(
            StackStatusFilter=[
                'CREATE_COMPLETE',
                'UPDATE_COMPLETE',
                'ROLLBACK_COMPLETE'
            ]
        )
        for page in iterator:
            stacks = page["StackSummaries"]
            for stack in stacks:
                if f"{self.cluster_name}-asg-" in stack['StackName'] \
                    and f"{self.cluster_name}-asg-{self.version}" not in stack['StackName']:
                    yield stack['StackName']

    def deactivate_new(self):
        """ Deactive the new cluster becuase it did not make it healthy """
        logger.info('Cluster fleet did not get added.')
        try:
            self.cf.update_stack(
                StackName=f"{self.cluster_name}-asg-{self.version}",
                Parameters=[{
                    'ParameterKey': 'Status',
                    'ParameterValue': 'inactive'
                }],
                UsePreviousTemplate=True,
                Capabilities=['CAPABILITY_IAM']
            )
        except botocore.exceptions.ClientError:
            logger.error("Best effort failure")


    def test_health(self):
        """ run the task and check its health """
        task_arn = self.ecs.describe_task_definition(
            taskDefinition=f"{self.cluster_vars['name']}-cluster-health-task"
        )['taskDefinition']['taskDefinitionArn']
        try:
            res = self.ecs.run_task(
                cluster=self.cluster_vars['name'],
                taskDefinition=task_arn,
                placementConstraints=[{
                    'type': 'memberOf',
                    'expression': f"attribute:asg_version == {self.version}"
                }],
                startedBy='cluster-health-check'
            )
            pprint(res)
            task_arn = res['tasks'][0]['taskArn']
        except botocore.exceptions.ClientError:
            logger.warning('Cluster instances failed to materialize')
            return 0
        health_checks = 0

        for _ in range(0, 60):
            try:
                status = self.ecs.describe_tasks(
                    cluster=self.cluster_vars['name'],
                    tasks=[task_arn]
                )
                status = status['tasks'][0]['lastStatus']
            except IndexError:
                status = 'MISSING'

            if status == 'RUNNING':
                if health_checks > 3:
                    logger.info('Task healthy!')
                    break
                health_checks += 1
            time.sleep(4)
            logger.info('Waiting on task...')
        res = self.ecs.stop_task(
            cluster=self.cluster_vars['name'],
            task=task_arn,
            reason='health check success'
        )
        logger.info("Stopping task.")
        return health_checks == 4




    def create_task(self):
        """ Creates a task definition in cloudformation for the stack """
        container_def = ContainerDefinition(
            Name='ClusterHealthContainerDef',
            Cpu=1,
            Memory=64,
            Image='ktruckenmiller/my-ip'
        )
        task = TaskDefinition(
            'ClusterHealthChecker',
            Family=f"{self.cluster_vars['name']}-cluster-health-task",
            ContainerDefinitions=[container_def]
        )
        self.t.add_resource(task)
