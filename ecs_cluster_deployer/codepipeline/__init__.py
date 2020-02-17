""" CodePipeline Generator """

import os
import logging
import yaml
from troposphere import Template, Parameter
from ecs_cluster_deployer.codepipeline.pipeline import (
    add_pipeline,
    get_repository_and_owner,
    get_branch
)
from ecs_cluster_deployer.codepipeline.pipeline_resources import add_pipeline_resources
from ecs_cluster_deployer.codepipeline.codebuild import add_packer_codebuild_job, add_deployer_codebuild_job
from ecs_cluster_deployer.codepipeline.github import GithubSecret
from ecs_cluster_deployer.runner import Runner

logger = logging.getLogger()
logging.basicConfig()
logger.setLevel(logging.INFO)

class AWSCodePipeline:
    """ AWS CodePipeline Generator for the ECS Cluster Deployer """
    def __init__(self):
        self.runner = None
        self.gh = GithubSecret()
        self.pipelines = [Pipeline(self.open_vars_file())]

    def open_vars_file(self):
        """ Open the vars file for the user """
        self.values_file = os.environ.get(
            'VALUES_FILE',
            'infra.yml'
        )
        with open(self.values_file, 'r') as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)

    def deploy(self):
        """ Deploy the code pipeline """
        self.gh.check_github_secret()
        for pipe_obj in self.pipelines:

            # Add webhook for github
            self.gh.add_webhook(pipe_obj.t)
            add_pipeline(
                pipe_obj.t,
                pipe_obj.environments,
                pipe_obj.name
            )
            add_pipeline_resources(pipe_obj.t, pipe_obj.name)
            add_packer_codebuild_job(pipe_obj.t, pipe_obj.name)
            add_deployer_codebuild_job(
                pipe_obj.t,
                pipe_obj.name,
                pipe_obj.environments
            )
            runner = Runner()
            runner.stack_name = pipe_obj.name + '-cluster-codepipeline'
            runner.template = pipe_obj.t
            runner.template.add_parameter(
                Parameter(
                    "Version",
                    Type="String"
                )
            )
            logger.info("Creating the CodePipeline stack ...")
            runner.push_cloudformation(runner.template)
            logger.info("Your ECS cluster is now coming online.")

class Pipeline: #pylint: disable=R0903
    """ Pipeline object """
    def __init__(self, file_obj):
        self.t = Template()
        self.name = file_obj.get('cluster').get('name')
        logging.info("Deploying AWS CodePipeline")
        self.environments = file_obj.get('environments', [''])
