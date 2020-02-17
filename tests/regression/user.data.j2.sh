set -ex
yum clean all && \
yum update -y && \
yum install -y aws-cli jq aws-cfn-bootstrap ecs-init amazon-efs-utils amazon-ssm-agent
