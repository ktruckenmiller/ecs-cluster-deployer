import pytest
from pprint import pprint
from unittest.mock import MagicMock, patch
from ecs_cluster_deployer.lambdas.metrics.cluster_metrics import (
    ClusterStats,
    ServiceStats,
    ContainerStats,
    ContainerInstanceStats
)

@pytest.fixture
def stat_obj():
    return ClusterStats('default')

def test_chunk(stat_obj):
    my_list = ['one', 'two', 'three']
    assert list(stat_obj._chunk(my_list, 2)) == [['one', 'two'], ['three']]

@pytest.fixture
def svc_obj():
    return ServiceStats()

def test_container_init():
    incoming_dict = {
        'name': 'boston',
        'cpu': 20,
    }
    container_obj = ContainerStats(incoming_dict)
    assert container_obj.name == 'boston'
    assert container_obj.cpu == 20
    assert container_obj.memory == 0
    # try with some defaults
    incoming_dict = {
        'name': 'boston',
        'cpu': 20,
        'memory': 256,
        'memoryReservation': 0
    }
    container_obj = ContainerStats(incoming_dict)
    assert container_obj.memory == 256

def test_service_init():
    svc = ServiceStats({
        'taskDefinition': 'arn:aws:ecs:us-west-2:601394826940:task-definition/drone-Task-1MUP2TV5749OQ:1',
        'desiredCount': 2
    })
    svc.ecs.describe_task_definition = MagicMock(return_value={
        'taskDefinition': {
            'containerDefinitions': [{
                'name': 'boston',
                'cpu': 20,
                'memoryReservation': 256
            }]
        }
    })
    assert svc.desired == 2
    assert svc.cpu_per_pod == 20
    assert svc.memory_per_pod == 256
    assert svc.cpu_requirement == 40
    assert svc.memory_requirement == 512

def test_container_instance_init():
    container_instance = ContainerInstanceStats({
        'registeredResources': [{
            'name': 'CPU',
            'integerValue': 2048
        }, {
            'name': 'MEMORY',
            'integerValue': 123
        }],
        'remainingResources': [{
            'name': 'CPU',
            'integerValue': 2
        }, {
            'name': 'MEMORY',
            'integerValue': 2
        }]
    })
    assert container_instance.total_cpu == 2048
    assert container_instance.total_memory == 123
    assert container_instance.available_cpu == 2
    assert container_instance.available_memory == 2
