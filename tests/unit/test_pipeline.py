from mock import MagicMock, patch, PropertyMock
import pytest
import datetime
import boto3
import botocore
from ecs_cluster_deployer.codepipeline import AWSCodePipeline
from ecs_cluster_deployer.codepipeline.pipeline import get_repository_and_owner, get_branch
from pprint import pprint


@pytest.fixture
@patch('botocore.client.BaseClient._make_api_call')
def base_obj(fake_api, monkeypatch):
    monkeypatch.setenv('VALUES_FILE', 'tests/regression/infra.yml')
    return AWSCodePipeline()

@patch('ecs_cluster_deployer.codepipeline.pipeline.get_branch')
@patch('ecs_cluster_deployer.codepipeline.Runner')
def test_init(fake_runner, fake_branch, monkeypatch):
    monkeypatch.setenv('VALUES_FILE', 'tests/regression/infra.yml')
    aws_cpln = AWSCodePipeline()
    fake_branch.return_value = 'boston'
    aws_cpln.gh.check_github_secret = MagicMock()
    aws_cpln.gh.add_webhook = MagicMock()
    aws_cpln.deploy()

@patch('ecs_cluster_deployer.codepipeline.pipeline.Repo')
def test_get_repo_and_owner(fake_remote):
    boston = MagicMock()
    boston.git.remote.return_value = 'git@github.com:ktruckenmiller/ecs-cluster-deployer.git'
    fake_remote.return_value = boston
    assert ('ktruckenmiller', 'ecs-cluster-deployer') == get_repository_and_owner()

    boston.git.remote.return_value = 'https://github.com/ktruckenmiller/jabba-the-hut.git'
    assert ('ktruckenmiller', 'jabba-the-hut') == get_repository_and_owner()
