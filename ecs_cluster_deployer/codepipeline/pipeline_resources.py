'''
This creates a pipeline role to be used for the cluster deployment.
'''
from troposphere import Sub
from troposphere.iam import Role, Policy
from ecs_cluster_deployer.utils import sanitize_cfn_resource_name

def add_pipeline_resources(t, name):
    '''
    This adds roles for the pipeline and other resources it might need.
    '''
    name = sanitize_cfn_resource_name(name)
    pipeline_role = Role(
        "PipelineRole",
        AssumeRolePolicyDocument={
            "Statement": [{
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Principal": {"Service": "codepipeline.amazonaws.com"},
            }]
        },
        Policies=[
            Policy(
                PolicyName="pipeline-base",
                PolicyDocument={
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "lambda:InvokeFunction",
                            "lambda:ListFunctions"
                        ],
                        "Resource": "*"
                    }, {
                        "Effect": "Allow",
                        "Action": [
                            "codebuild:BatchGetBuilds",
                            "codebuild:StartBuild"
                        ],
                        "Resource": "*"
                    }, {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:List*"
                        ],
                        "Resource": [
                            Sub("arn:aws:s3:::ecs-cluster-deployer-" \
                                "${AWS::AccountId}-${AWS::Region}"),
                            Sub("arn:aws:s3:::ecs-cluster-deployer-"\
                                "${AWS::AccountId}-${AWS::Region}/*")
                        ]
                    }]
                }
            )
        ]
    )
    t.add_resource(pipeline_role)
