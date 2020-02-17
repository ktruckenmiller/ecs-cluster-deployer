from ecs_cluster_deployer.healthcheck import HealthCheck
from mock import patch
import pytest
from pprint import pprint
from unittest.mock import MagicMock

class ECSClusterObj(object):
    def __init__(self):
        self.region = 'us-west-2'
        self.version = 'my-version'
        self.base = {
            'cluster': {
                'name': 'kloudcover'
            }
        }

@pytest.fixture
@patch('ecs_cluster_deployer.healthcheck.botocore.client.BaseClient._make_api_call')
def health_obj(fake_api):
    return HealthCheck(ECSClusterObj())

def test_health_init(health_obj):
    health_obj.cf.list_stacks = MagicMock(return_value={
        'StackSummaries': [{
            'StackName': 'kloudcover-asg-something'
        },{
            'StackName': 'kloudcover-asg-my-version'
        }]
    })
    health_obj.ecs = MagicMock()
    assert list(health_obj.get_old_stacks()) == ['kloudcover-asg-something']

def test_deactivate(health_obj):
    health_obj.cf.update_stack = MagicMock()
    health_obj.get_old_stacks = MagicMock(return_value=['kloudcover-asg-39d7327'])
    health_obj.deactivate_old()
    health_obj.cf.update_stack.assert_called_with(
        Parameters=[{'ParameterKey': 'Status', 'ParameterValue': 'inactive'}],
        StackName='kloudcover-asg-39d7327',
        UsePreviousTemplate=True,
        Capabilities=['CAPABILITY_IAM']
    )

# def test_create_task(health_obj):
#     health_obj.create_task()
#     assert health_obj.t.resources['ClusterHealthChecker'].to_dict() == {
#         'Properties': {'ContainerDefinitions': [{'Cpu': 0,
#         'Image': 'ktruckenmiller/my-ip',
#         'Name': 'ClusterHealthContainerDef'}]},
#         'Type': 'AWS::ECS::TaskDefinition'}
#
# def test_create_deploy(health_obj):
#     health_obj.deploy()
#     healthy = health_obj.test_health()
#     if healthy:
#         print('stack is healthy!')
#     else:
#         print('Stack is not healthy')
