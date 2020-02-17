"""
Entrypoint for the cluster deployer

This file orchestrates the higher level functions
"""
import sys
import logging
from ecs_cluster_deployer.cluster import ECSCluster
from ecs_cluster_deployer.vars import ECSVars
from ecs_cluster_deployer.compute import EC2Instances
from ecs_cluster_deployer.healthcheck import HealthCheck
from ecs_cluster_deployer.codepipeline import AWSCodePipeline


logger = logging.getLogger()
logging.basicConfig()
logger.setLevel(logging.INFO)


def put_pipeline():
    """ Sets up cluster codepipeline """
    pipeline = AWSCodePipeline()
    pipeline.deploy()

def deploy():
    """ Deploys the ECS cluster """
    cluster_obj = ECSVars()

    # cluster deploy
    ECSCluster(cluster_obj)
    cluster_obj.deploy()

    # asg / spot deploy
    ec2_obj = ECSVars()
    EC2Instances(ec2_obj)
    ec2_obj.deploy()


    # healthcheck
    cluster_obj = ECSVars()
    health_obj = HealthCheck(cluster_obj)
    health_obj.deploy()
    healthy = health_obj.test_health()
    if healthy:
        logger.info('ECS stack is healthy!!')
        health_obj.deactivate_old()
        # find any stacks that are not the healthy one
        # update stack to inactive
        # step function to remove empty stacks
    else:
        # set this stack to inactive
        # step function to remove empty stacks
        health_obj.deactivate_new()
        logger.error('Stack is not healthy')
        sys.exit(1)
