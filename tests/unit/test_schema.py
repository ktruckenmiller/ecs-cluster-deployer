from ecs_cluster_deployer.schema import validate
import pytest
from pprint import pprint
import cerberus
@pytest.fixture
def cluster_obj():
    return {
        "cluster": {
            "name": "boston",
            "vpc": "vpc-849531e0"
        }
    }


def test_validate(cluster_obj):
    validate.validate_cluster(cluster_obj)
    cluster_obj['cluster'].pop('name')
    with pytest.raises(cerberus.schema.SchemaError) as e_info:
        validate.validate_cluster(cluster_obj)

# def test_more_values(cluster_obj):
#     pprint(cluster_obj)
#     cluster_obj['cluster'].update({
#         "ami": 'ami-983e4e3e4',
#         "subnets": [
#             'subnet-ie8e9ee1eeeee'
#         ]
#     })
#     validate.validate_cluster(cluster_obj)
