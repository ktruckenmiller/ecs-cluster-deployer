"""
    Adds the codebuild jobs for packer and for deploying the clusters
"""
import os
from troposphere import Ref, Sub
from troposphere.codebuild import Artifacts, Environment, Source, Project
from troposphere.iam import Role, Policy, InstanceProfile
from ecs_cluster_deployer.utils import sanitize_cfn_resource_name


def add_deployer_codebuild_job(t, name, environments):
    """
    Adds deployer role to the codebuild job for ecs cluster deployer
    """
    with open(os.path.dirname(os.path.realpath(__file__)) + "/buildspecs/cluster_deployer.yml") as spec:
        build_spec = spec.read()

    cfn_name = sanitize_cfn_resource_name(name)

    deployer_role = Role(
        "CodeBuildClusterDeployerRole",
        AssumeRolePolicyDocument={
            "Statement": [{
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Principal": {"Service": [
                    "codebuild.amazonaws.com"
                ]}
            }]
        },
        Policies=[
            Policy(
                PolicyName="codebuild-cluster-deployer",
                PolicyDocument={
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "ec2:CreateSecurityGroup",
                            "ec2:DeleteSecurityGroup",
                            "ec2:CreateTags",
                            "ec2:AuthorizeSecurityGroupIngress",
                            "ec2:RequestSpotFleet",
                            "ec2:CancelSpotFleetRequests",
                            "ec2:Describe*",
                            "ec2:CreateKeyPair",
                            "ec2:RevokeSecurityGroupIngress",
                            "iam:CreateRole",
                            "iam:CreateInstanceProfile",
                            "iam:DeleteInstanceProfile",
                            "iam:RemoveRoleFromInstanceProfile",
                            "iam:DeleteInstanceProfile",
                            "iam:AddRoleToInstanceProfile",
                            "iam:DeleteRole",
                            "iam:DeleteRolePolicy",
                            "iam:PutRolePolicy",
                            "iam:List*",
                            "iam:Get*",
                            "iam:PassRole",
                            "logs:*",
                            "lambda:*",
                            "events:*",
                            "ecs:*",
                            "cloudformation:ListStacks"
                        ],
                        "Resource": "*"
                    }, {
                        "Effect": "Allow",
                        "Action": [
                            "ssm:PutParameter",
                            "ssm:GetParameter",
                            "ssm:DeleteParameter",
                            "ssm:AddTagsToResource",
                        ],
                        "Resource": [
                            {"Fn::Sub":"arn:aws:ssm:${AWS::Region}:${AWS::AccountId}:parameter/ecs-maestro/*"}
                        ]
                    }, {
                        "Effect": "Allow",
                        "Action": ["cloudformation:*"],
                        "Resource": [
                            f"arn:aws:cloudformation:*:*:stack/{name}*"
                        ]
                    }, {
                        "Effect": "Allow",
                        "Action": ["s3:*"],
                        "Resource": [{
                            "Fn::Sub": "arn:aws:s3:::ecs-cluster-deployer-${AWS::AccountId}-${AWS::Region}"
                        }, {
                            "Fn::Sub": "arn:aws:s3:::ecs-cluster-deployer-${AWS::AccountId}-${AWS::Region}/*"
                        }]
                    }]
                }
            )
        ]
    )

    for environment in environments:
        t.add_resource(Project(
            f"Deploy{cfn_name}{environment.title()}",
            Name=f"Deploy{cfn_name}{environment.title()}",
            Artifacts=Artifacts(Type='CODEPIPELINE'),
            Environment=Environment(
                ComputeType="BUILD_GENERAL1_SMALL",
                Type="LINUX_CONTAINER",
                Image="aws/codebuild/standard:2.0",
                EnvironmentVariables=[{
                    'Name': 'CLUSTER_NAME',
                    'Value': name
                }, {
                    'Name': 'ENVIRONMENT',
                    'Value': environment
                }, {
                    'Name': 'ECS_CLUSTER_DEPLOYER_VERSION',
                    'Value': os.environ.get('ECS_CLUSTER_DEPLOYER_VERSION')
                }, {
                    'Name': 'VALUES_FILE',
                    'Value': os.environ.get('VALUES_FILE', 'infra.yml')
                }],
                PrivilegedMode=True

            ),
            ServiceRole=Ref(deployer_role),
            Source=Source(
                Type="CODEPIPELINE",
                BuildSpec=build_spec
            )
        ))

    t.add_resource(deployer_role)

def add_packer_codebuild_job(t, name, environment=None):
    """ Add the packer AMI build to the codebuild job """
    cfn_name = sanitize_cfn_resource_name(name)
    with open(os.path.dirname(os.path.realpath(__file__)) + "/buildspecs/packer.yml") as spec:
        build_spec = spec.read()

    codebuild_job_environments = [{
        'Name': 'CLUSTER_NAME',
        'Value': name
    }]
    if environment:
        codebuild_job_environments.append({'Name': 'ENVIRONMENT', 'Value': environment})

    PackerRole = Role(
        "CodeBuildPackerRole",
        AssumeRolePolicyDocument={
            "Statement": [{
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Principal": {"Service": [
                    "codebuild.amazonaws.com",
                    "ec2.amazonaws.com"
                ]},
            }]
        },
        Policies=[
            Policy(
                PolicyName="codebuild-packer",
                PolicyDocument={
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "ec2:AttachVolume",
                            "ec2:AuthorizeSecurityGroupIngress",
                            "ec2:CopyImage",
                            "ec2:CreateImage",
                            "ec2:CreateKeypair",
                            "ec2:CreateSecurityGroup",
                            "ec2:CreateSnapshot",
                            "ec2:CreateTags",
                            "ec2:CreateVolume",
                            "ec2:DeleteKeyPair",
                            "ec2:DeleteSecurityGroup",
                            "ec2:DeleteSnapshot",
                            "ec2:DeleteVolume",
                            "ec2:DeregisterImage",
                            "ec2:Describe*",
                            "ec2:DetachVolume",
                            "ec2:GetPasswordData",
                            "ec2:ModifyImageAttribute",
                            "ec2:ModifyInstanceAttribute",
                            "ec2:ModifySnapshotAttribute",
                            "ec2:RegisterImage",
                            "ec2:RunInstances",
                            "ec2:StopInstances",
                            "ec2:TerminateInstances",
                            "iam:PassRole"
                        ],
                        "Resource": "*"
                    }, {
                        "Effect": "Allow",
                        "Action": ["logs:*"],
                        "Resource": "*"
                    }, {
                        "Effect": "Allow",
                        "Action": [
                            "ssm:GetParametersByPath",
                            "ssm:GetParameters",
                            "ssm:GetParameter"
                        ],
                        "Resource": [
                            "arn:aws:ssm:*:*:parameter/aws/service/ecs*"
                        ]
                    }, {
                        "Effect": "Allow",
                        "Action": "s3:*",
                        "Resource": [{
                            "Fn::Sub": "arn:aws:s3:::ecs-cluster-deployer-${AWS::AccountId}-${AWS::Region}"
                        }, {
                            "Fn::Sub": "arn:aws:s3:::ecs-cluster-deployer-${AWS::AccountId}-${AWS::Region}/*"
                        }]
                    }]
                }
            )
        ]
    )

    PackerInstanceProfile = InstanceProfile(
        "PackerInstanceProfile",
        InstanceProfileName=f"{cfn_name}PackerInstanceProfile",
        Roles=[Ref(PackerRole)]
    )
    environment = Environment(
        ComputeType="BUILD_GENERAL1_SMALL",
        Type="LINUX_CONTAINER",
        Image="aws/codebuild/standard:2.0",
        EnvironmentVariables=codebuild_job_environments,
        PrivilegedMode=True

    )
    PackerCodebuild = Project(
        "PackerAMIBuilder",
        Name=f"{cfn_name}PackerAMIBuilder",
        Artifacts=Artifacts(Type='CODEPIPELINE'),
        Environment=environment,
        ServiceRole=Ref(PackerRole),
        Source=Source(
            Type="CODEPIPELINE",
            BuildSpec=Sub(build_spec)
        )
    )
    t.add_resource(PackerRole)
    t.add_resource(PackerCodebuild)
    t.add_resource(PackerInstanceProfile)
