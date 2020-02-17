set -ex
yum clean all && \
yum update -y && \
yum install -y aws-cli jq aws-cfn-bootstrap ecs-init amazon-efs-utils amazon-ssm-agent

stop ecs
service docker stop

## Remove Device Mapper
EC2_AVAIL_ZONE=`curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone`
EC2_REGION="`echo \"$EC2_AVAIL_ZONE\" | sed 's/[a-z]$//'`"
INSTANCE_ID=$(curl http://169.254.169.254/latest/meta-data/instance-id)
VOLUME=$(aws ec2 describe-volumes --filter Name=attachment.instance-id,Values=${INSTANCE_ID} --region ${EC2_REGION} --query 'Volumes[*].Attachments[?Device==`/dev/xvdcz`].VolumeId' --output text)
vgchange -an docker
aws ec2 detach-volume --volume-id ${VOLUME} --region ${EC2_REGION}
sleep 20
aws ec2 delete-volume --volume-id ${VOLUME} --region ${EC2_REGION}

# aws ec2 --- lookup device and unmount
echo 'DOCKER_STORAGE_OPTIONS="--storage-driver overlay2"' > /etc/sysconfig/docker-storage
service docker restart
