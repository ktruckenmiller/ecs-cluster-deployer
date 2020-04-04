import pytest
import boto3
from moto import mock_ec2, mock_sts
from ecs_cluster_deployer.vars import ECSVars
from ecs_cluster_deployer.compute import EC2Instances

@pytest.fixture
@mock_ec2
@mock_sts
def ecs_inst(monkeypatch):
    monkeypatch.setenv('VERSION', '1')
    monkeypatch.setenv('VALUES_FILE', 'tests/regression/base.yml')
    monkeypatch.setenv('AMI', 'ami-id')
    ecs_vars = ECSVars()
    return EC2Instances(ecs_vars)

def test_init(ecs_inst):
    parameters = [
        "S3Bucket",
        "S3Prefix",
        "Version",
        "ClusterName",
        "Status",
        "ScaleOutAdustment",
        "ScaleInAdjustment",
        "ASGCapacity",
        "ASGMaxSize",
        "ASGMinSize",
        "SpotWeight",
        "SpotMaxWeight",
        "SpotMinWeight",
        "SpotTaskThresholdOut",
        "SpotTaskThresholdIn"
    ]
    resources = [
        "IncomingSg",
        "ECSPort22SG",
        "SpotFleetRole",
        "SpotFleetMain",
        "ScaleMain",
        "AutoscalingRole",
        "ScalingLambdaMain",
        "CronScalingMain",
        "ScalePermMain",
        "ASGLaunchConfigReserved",
        "ASGReserved"
    ]
    for param in ecs_inst.template.parameters:
        assert param in parameters

    for resource in ecs_inst.template.resources:
        assert resource in resources

def test_scale_task_threshold(ecs_inst):
    assert ecs_inst.template.parameters['SpotTaskThresholdIn'].properties.get("Default") == '15'
    assert ecs_inst.template.parameters['SpotTaskThresholdOut'].properties.get("Default") == '1'
