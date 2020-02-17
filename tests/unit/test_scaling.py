from mock import MagicMock, patch, PropertyMock
import pytest
import datetime
import boto3
import botocore
from ecs_cluster_deployer.lambdas.scaling.scale_spot import SpotScaler, lambda_handler
from pprint import pprint


@pytest.fixture
@patch('botocore.client.BaseClient._make_api_call')
def base_obj(fake_api):
    spot_scaler = SpotScaler()
    spot_scaler.ec2 = MagicMock()
    spot_scaler.ssm = MagicMock()
    spot_scaler.cw = MagicMock()
    spot_scaler.ssm_path = '/ecs/my-cluster/scaletime'

    return spot_scaler

@pytest.fixture
def mock_date():
    return datetime.datetime.now()

def target_cap(num):
    return {
        'SpotFleetRequestConfigs':[{'SpotFleetRequestConfig': {
            'TargetCapacity': num
        }}]
    }

def test_metric(base_obj):
    base_obj.scale_metric = 'Schedulable Cluster Tasks'
    base_obj.cluster_name = 'kloudcover'
    print(base_obj.get_metric())

@patch('ecs_cluster_deployer.lambdas.scaling.scale_spot.SpotScaler.deactivate_stack')
@patch('ecs_cluster_deployer.lambdas.scaling.scale_spot.SpotScaler.get_metric')
@patch('ecs_cluster_deployer.lambdas.scaling.scale_spot.SpotScaler.scale')
def test_lambda_handler(fake_scale, fake_metric, fake_deactivate,  monkeypatch):
    monkeypatch.setenv('STATUS', 'active')
    monkeypatch.setenv('CLUSTER_NAME', 'boston')
    fake_metric.return_value = 1
    lambda_handler({}, {})
    fake_scale.assert_called_with(2)

    fake_metric.return_value = 8
    lambda_handler({}, {})
    fake_scale.assert_called_with(-1)

@patch('ecs_cluster_deployer.lambdas.scaling.scale_spot.SpotScaler.deactivate_stack')
@patch('ecs_cluster_deployer.lambdas.scaling.scale_spot.SpotScaler.get_metric')
@patch('ecs_cluster_deployer.lambdas.scaling.scale_spot.SpotScaler.scale')
def test_lambda_handler_deactive(fake_scale, fake_metric, fake_deactivate,  monkeypatch):
    monkeypatch.setenv('STATUS', 'inactive')
    monkeypatch.setenv('CLUSTER_NAME', 'boston')
    lambda_handler({}, {})
    fake_deactivate.assert_called_with()
    fake_scale.assert_not_called()

def test_enabler_active(monkeypatch):
    monkeypatch.setenv('ENABLED', 'false')
    monkeypatch.setenv('CLUSTER_NAME', 'boston')
    monkeypatch.setenv('STATUS', 'active')
    spot_scaler = SpotScaler()
    assert spot_scaler.deactivate == False
    assert spot_scaler.enabled == False

    monkeypatch.setenv('STATUS', 'inactive')
    monkeypatch.setenv('ENABLED', 'true')
    spot_scaler = SpotScaler()
    assert spot_scaler.deactivate
    assert spot_scaler.enabled

def test_cloudwatch(base_obj):
    base_obj.cluster_name = 'kloudcover'
    base_obj.cw.get_metric_statistics.return_value = {
        'Datapoints':[{'Average': 0.0}]
    }
    assert base_obj.get_metric() == 0.0

@patch('botocore.client.BaseClient._make_api_call')
def test_deactivate_stack(base_obj):
    base_obj.version = '0.0.6'
    base_obj.cluster_name = 'kloudcover'
    base_obj.ec2 = boto3.client('ec2')
    base_obj.ssm = boto3.client('ssm')
    base_obj.spot_fleet = 'sfr-529bc17b-6004-4c88-99ea-3cee507e9fd3'
    base_obj.ssm_path = '/ecs/kloudcover/{}/scaletime'.format(base_obj.version)
    base_obj.deactivate_stack()
    base_obj.set_date()


def test_test_get_date(base_obj, mock_date):
    base_obj.ssm.get_parameters.return_value= {
        'Parameters': [{
            'Name': '/ecs/my-cluster/scaletime',
            'Value': '2018-02-11 15:04:48.926316'
        }]
    }
    assert datetime.datetime.utcnow() > base_obj.last_scale_date()

def test_get_date_initial(base_obj, mock_date):
    base_obj.ssm.get_parameters.return_value= {
        'Parameters': [{
            'Name': '/ecs/my-cluster/scaletime',
            'Value': 'boston'
        }]
    }
    assert datetime.datetime.utcnow() > base_obj.last_scale_date()

def test_scale(base_obj):
    base_obj.last_scale_date = MagicMock(
        return_value=datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
    )
    base_obj.has_running_tasks = MagicMock(return_value=False)
    base_obj.set_date = MagicMock()

    base_obj.ec2.describe_spot_fleet_requests.return_value = target_cap(1)
    base_obj.spot_fleet = 'sfr-3fa4e925-9f57-483d-be98-d6a14afd81f4'

    base_obj.scale(2)

    base_obj.ec2.modify_spot_fleet_request.assert_called_once_with(
        SpotFleetRequestId=base_obj.spot_fleet,
        TargetCapacity=3
    )
    base_obj.scale(-1)
    base_obj.scale(-9.0)
    assert base_obj.ec2.modify_spot_fleet_request.call_count == 1

def test_delete(base_obj, monkeypatch):
    monkeypatch.setenv('CLUSTER_NAME', 'kloudcover')
    base_obj.lambdy = MagicMock()
    base_obj.version = 'version1'
    base_obj.cluster_name = 'boston'
    base_obj.delete_stack()
    base_obj.lambdy.invoke.assert_called_with(
        FunctionName='KloudcoverASGCleanupLambda',
        Payload='{"asg_stack": "boston-asg-version1"}'
    )

def test_delete(base_obj, monkeypatch):
    monkeypatch.setenv('CLUSTER_NAME', 'scaling-kloudcover')
    base_obj.lambdy = MagicMock()
    base_obj.version = 'version1'
    base_obj.cluster_name = 'boston'
    base_obj.delete_stack()
    base_obj.lambdy.invoke.assert_called_with(
        FunctionName='ScalingKloudcoverASGCleanupLambda',
        Payload='{"asg_stack": "boston-asg-version1"}'
    )

def test_has_tasks(base_obj, monkeypatch):
    base_obj.ecs.list_tasks = MagicMock(return_value={'taskArns': []})
    base_obj.has_running_tasks() == False
    base_obj.ecs.list_tasks = MagicMock(return_value={'taskArns': ['1', '2']})
    base_obj.has_running_tasks() == True
