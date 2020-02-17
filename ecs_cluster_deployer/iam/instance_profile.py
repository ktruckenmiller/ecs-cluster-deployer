""" Methods for adding instance profiles """
from troposphere import (
    Ref, GetAtt
)
from troposphere.iam import (
    Role,
    Policy,
    InstanceProfile
)

def add_instance_profile_to_template(template):
    """ Adds instance profile to the ecs container instances """
    template.add_resource(Role(
        "ECSInstanceRole",
        AssumeRolePolicyDocument={
            "Statement": [{
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Principal": {"Service": "ec2.amazonaws.com"},
            }]
        },
        Policies=[Policy(
            PolicyName="ssm-agent",
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ssm:DescribeAssociation",
                            "ssm:GetDeployablePatchSnapshotForInstance",
                            "ssm:GetDocument",
                            "ssm:DescribeDocument",
                            "ssm:GetManifest",
                            "ssm:GetParameter",
                            "ssm:GetParameters",
                            "ssm:ListAssociations",
                            "ssm:ListInstanceAssociations",
                            "ssm:PutInventory",
                            "ssm:PutComplianceItems",
                            "ssm:PutConfigurePackageResult",
                            "ssm:UpdateAssociationStatus",
                            "ssm:UpdateInstanceAssociationStatus",
                            "ssm:UpdateInstanceInformation"
                        ],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ssmmessages:CreateControlChannel",
                            "ssmmessages:CreateDataChannel",
                            "ssmmessages:OpenControlChannel",
                            "ssmmessages:OpenDataChannel"
                        ],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ec2messages:AcknowledgeMessage",
                            "ec2messages:DeleteMessage",
                            "ec2messages:FailMessage",
                            "ec2messages:GetEndpoint",
                            "ec2messages:GetMessages",
                            "ec2messages:SendReply"
                        ],
                        "Resource": "*"
                    }
                ]
            }
        ), Policy(
            PolicyName="ecs-policy",
            PolicyDocument={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "ec2:DescribeTags",
                            "ecs:CreateCluster",
                            "ecs:DeregisterContainerInstance",
                            "ecs:DiscoverPollEndpoint",
                            "ecs:Poll",
                            "ecs:RegisterContainerInstance",
                            "ecs:StartTelemetrySession",
                            "ecs:UpdateContainerInstancesState",
                            "ecs:Submit*",
                            "ecr:GetAuthorizationToken",
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchGetImage",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents"
                        ],
                        "Resource": "*"
                    }
                ]
            }
        )]
    ))
    template.add_resource(InstanceProfile(
        "ECSInstanceProfile",
        Roles=[Ref("ECSInstanceRole")]
    ))
    return GetAtt("ECSInstanceProfile", "Arn")
