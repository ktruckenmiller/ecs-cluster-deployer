'''
Deploys lambda functions that will clean up a cluster.

This will only clean up clusters that have a specific version.
'''
from troposphere import Sub, GetAtt
from troposphere.awslambda import Function, Code
from troposphere.iam import Role, Policy

def add_asg_cleanup(template, cluster_name):
    '''
    Deploys a ASG cleanup function that removes stacks of clusters that are
    inactive and have no nodes
    '''
    cleanup_lambda = Function(
        f"{cluster_name}ASGCleanupLambda",
        Code=Code(
            S3Bucket=Sub("${S3Bucket}"),
            S3Key=Sub("${S3Prefix}/deployment.zip")
        ),
        FunctionName=f"{cluster_name}ASGCleanupLambda",
        Handler="cleanup.cleanup.lambda_handler",
        Role=GetAtt("ASGCleanupLambdaRole", "Arn"),
        Runtime="python3.7",
        MemorySize=128,
        Timeout=40
    )
    cleanup_role = Role(
        "ASGCleanupLambdaRole",
        AssumeRolePolicyDocument={
            "Statement": [{
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Principal": {"Service": "lambda.amazonaws.com"},
            }]
        },
        Policies=[
            Policy(
                PolicyName="RemoveResoruces",
                PolicyDocument={
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "cloudwatch:*",
                            "autoscaling:*",
                            "events:*",
                            "iam:DeleteRole",
                            "iam:DeletePolicy",
                            "iam:Get*",
                            "iam:List*",
                            "lambda:*",
                            "iam:DetachRolePolicy",
                            "iam:DeleteInstanceProfile",
                            "iam:DeleteRolePolicy",
                            "iam:RemoveRoleFromInstanceProfile",
                            "application-autoscaling:*",
                            "ec2:*",
                            "logs:*"
                        ],
                        "Resource": "*"
                    }, {
                        "Effect": "Allow",
                        "Action": [
                            "cloudformation:DeleteStack"
                        ],
                        "Resource": [
                            {"Fn::Sub": "arn:aws:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ClusterName}-asg-*"}
                        ]
                    }, {
                        "Effect": "Allow",
                        "Action": [
                            "ssm:DeleteParameter"
                        ],
                        "Resource": [
                            {"Fn::Sub": "arn:aws:ssm:${AWS::Region}:${AWS::AccountId}:parameter/ecs-maestro/${ClusterName}/*"}
                        ]
                    }]
                }
            )
        ]
    )
    template.add_resource(cleanup_lambda)
    template.add_resource(cleanup_role)
