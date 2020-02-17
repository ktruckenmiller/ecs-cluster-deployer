from ecs_cluster_deployer import utils
from unittest.mock import patch

def test_sanitize_name():
    assert utils.sanitize_cfn_resource_name('my-name') == "MyName"
