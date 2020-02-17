import pytest
import yaml
import botocore
from unittest.mock import MagicMock
from ecs_cluster_deployer.vars import ECSVars
from ecs_cluster_deployer.compute import EC2Instances


@pytest.fixture
def ecs_inst(monkeypatch):
    monkeypatch.setenv('VERSION', '1')
    monkeypatch.setenv('VALUES_FILE', 'tests/regression/base.yml')
    monkeypatch.setenv('AMI', 'ami-id')
    vars = ECSVars()

    return EC2Instances(vars)


def test_keypair(ecs_inst):
    ecs_inst.ssm = MagicMock(return_value={
        "Parameter": {"Value": "boston"}
    })
    ecs_inst.ec2 = MagicMock()
    ecs_inst.cluster['keypair'] = None
    boston = ecs_inst.keypair
    ecs_inst.ssm.get_parameter.assert_called_with(
        Name='/ecs-maestro/scaling-kloudcover/keypair'
    )

def test_keypair_create(ecs_inst):
    ecs_inst.ssm = MagicMock()
    error = {
        'Error': {
            'Code': '123',
            'Message': 'stuff'
        }

    }
    ecs_inst.ssm.get_parameter.side_effect = botocore.exceptions.ClientError(error, 'GetParameter')
    ecs_inst.ec2 = MagicMock()
    ecs_inst.cluster['keypair'] = None
    with pytest.raises(botocore.exceptions.ClientError) as err:
        boston = ecs_inst.keypair
        ecs_inst.ssm.get_parameter.assert_called_with(
            Name='/ecs-maestro/scaling-kloudcover/keypair'
        )

    # now change the error to be a continuation Error
    error['Error']['Code'] = 'ParameterNotFound'
    ecs_inst.create_key = MagicMock()
    ecs_inst.ssm.get_parameter.side_effect = botocore.exceptions.ClientError(error, 'GetParameter')
    boston = ecs_inst.keypair
    ecs_inst.ssm.get_parameter.assert_called_with(
        Name='/ecs-maestro/scaling-kloudcover/keypair'
    )
    ecs_inst.create_key.assert_called()

def test_create_key(ecs_inst):
    ecs_inst.ssm = MagicMock()
    ecs_inst.ec2.create_key_pair = MagicMock(return_value={
        'KeyMaterial': 'boston'
    })
    ecs_inst.create_key()
    ecs_inst.ec2.create_key_pair.assert_called_with(KeyName='ecs-maestro-scaling-kloudcover')
    ecs_inst.ssm.put_parameter.assert_called_with(
        Description='ClusterMaestro ssh key for scaling-kloudcover',
        Name='/ecs-maestro/scaling-kloudcover/keypair',
        Type='SecureString',
        Value='boston'
    )
