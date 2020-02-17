from mock import MagicMock, patch, PropertyMock
import pytest
import datetime
import boto3
import botocore
from ecs_cluster_deployer.lambdas.scaling.scale_spot import SpotScaler, lambda_handler
from pprint import pprint

@pytest.fixture
@patch('ecs_cluster_deployer.lambdas.scaling.scale_spot.botocore.client.BaseClient._make_api_call')
def base_obj(fake_api, monkeypatch):
    monkeypatch.setenv('VERSION', 'boston')
    monkeypatch.setenv('CLUSTER_NAME', 'boston')
    spot_scaler = SpotScaler()
    spot_scaler.ssm_path = '/ecs/my-cluster/scaletime'

    return spot_scaler


def test_deactivate(base_obj):
    base_obj.cluster_name = 'asdf'
    base_obj.version = 'asdf'
    base_obj.ecs.list_container_instances = MagicMock(return_value={
        'containerInstanceArns': []
    })
    assert base_obj.cluster_version_empty()

    base_obj.ecs.list_container_instances = MagicMock(return_value={
        'containerInstanceArns': ['boston']
    })
    assert base_obj.cluster_version_empty() == False

def test_remove_stack(base_obj):
    base_obj.cluster_name = 'sfdf'
    base_obj.version = 'dfasdf'
    base_obj.ecs.list_container_instances = MagicMock(return_value={
        'containerInstanceArns': []
    })
