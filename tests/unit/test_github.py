from mock import MagicMock, patch, PropertyMock
import pytest
import datetime
import boto3
import botocore
from ecs_cluster_deployer.codepipeline.github import GithubSecret
from pprint import pprint

@pytest.fixture
@patch('ecs_cluster_deployer.codepipeline.github.botocore.client.BaseClient._make_api_call')
def base_obj(fake_api):
    return GithubSecret()


def test_list_secret(base_obj):
    base_obj.sm.list_secrets = MagicMock(return_value={'SecretList': []})
    assert list(base_obj.find_github_secret('boston')) == []
    base_obj.sm.list_secrets = MagicMock(side_effect=[
        {
            'SecretList': [{
                'Name': 'Github'
            }],
            'NextToken': 'boston'
        },
        {
            'SecretList': [{
                'Name': 'Synergy'
            }]
        }
    ])
    secrets = list(base_obj.find_github_secret('Github'))
    assert secrets == [{'Name': 'Github'}]

@patch('ecs_cluster_deployer.codepipeline.github.input')
def test_check_secret(fake_input, base_obj):
    fake_input.side_effect = ['y', 'my-secret', 'y', 'dfsdf']
    # base_obj.find_github_secret = MagicMock(return_value = [{"Name": "GithubToken"}])
    # assert base_obj.check_github_secret() == None
    # base_obj.create_github_secret = MagicMock()
    # base_obj.find_github_secret = MagicMock(return_value = [])
    # base_obj.check_github_secret()
    # fake_input.assert_called_with('Please Enter Github Personal Access Token for Codepipeline: ')

@patch('ecs_cluster_deployer.codepipeline.github.input')
def test_create_github_secret(fake_input, base_obj):
    base_obj.sm.create_secret = MagicMock()
    fake_input.return_value = 'pat-token-1234'
    base_obj.create_github_secret('my-secret', '1234')
    base_obj.sm.create_secret.assert_called_with(
        Description='Github oauth personal access token for CI/CD',
        KmsKeyId='1234',
        Name='my-secret',
        SecretString='pat-token-1234'
    )

    ''' No kms '''
    base_obj.sm.create_secret = MagicMock()
    fake_input.return_value = 'pat-token-1234'
    base_obj.create_github_secret('my-secret', None)
    base_obj.sm.create_secret.assert_called_with(
        Description='Github oauth personal access token for CI/CD',
        Name='my-secret',
        SecretString='pat-token-1234'
    )
