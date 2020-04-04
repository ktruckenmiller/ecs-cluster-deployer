"""
Adds troposphere methods for adding scaling to a cluster
"""
from troposphere.awslambda import Function, Code, Environment, Permission
from troposphere import Ref, Sub, GetAtt
from troposphere.iam import Role, Policy
from troposphere.events import Target, Rule
from troposphere.ssm import Parameter
from ecs_cluster_deployer.utils import sanitize_cfn_resource_name

def add_scaling(spot_fleet, template, cluster_name):
    """ Add scaling resources to a cluster """
    ssm_param = Parameter(
        'Scale{}'.format(sanitize_cfn_resource_name(spot_fleet.get('name'))),
        Type="String",
        Value="0",
        Name=Sub("/ecs-maestro/${ClusterName}/${Version}/scaletime")
    )
    template.add_resource(ssm_param)
    function_name = sanitize_cfn_resource_name(cluster_name)
    autoscaling_role = Role(
        "AutoscalingRole",
        AssumeRolePolicyDocument={
            "Statement": [{
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Principal": {"Service": "lambda.amazonaws.com"},
            }]
        },
        Policies=[
            Policy(
                PolicyName="ec2-spot-fleet-scaler",
                PolicyDocument={
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "cloudwatch:Get*",
                            "ec2:DescribeSpotFleetRequests",
                            "ec2:ModifySpotFleetRequest",
                            "logs:*",
                            "ecs:ListContainerInstances",
                            "ecs:Update*",
                            "ecs:ListTasks",
                            "s3:GetEncryptionConfiguration"
                        ],
                        "Resource": "*"
                    }, {
                        "Effect": "Allow",
                        "Action": [
                            "ssm:Get*",
                            "ssm:Put*",
                            "ssm:Delete*"
                        ],
                        "Resource": [
                            {"Fn::Sub": "arn:aws:ssm:${AWS::Region}:${AWS::AccountId}:parameter/ecs-maestro/${ClusterName}/*"}
                        ]
                    }]
                }
            ),
            Policy(
                PolicyName="DeleteStack",
                PolicyDocument={
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "lambda:InvokeFunction",
                        ],
                        "Resource": [
                            {"Fn::Sub": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:"+function_name+"ASGCleanupLambda"}]
                    }]
                }
            )
        ]
    )
    template.add_resource(autoscaling_role)
    scaling_lambda = Function(
        'ScalingLambda{}'.format(sanitize_cfn_resource_name(spot_fleet.get('name'))),
        Code=Code(
            S3Bucket=Sub("${S3Bucket}"),
            S3Key=Sub("${S3Prefix}/deployment.zip")
        ),
        Handler="scaling.scale_spot.lambda_handler",
        Role=GetAtt(autoscaling_role, "Arn"),
        Environment=Environment(
            Variables={
                "CLUSTER_NAME": Sub("${ClusterName}"),
                "SPOT_FLEET": Ref(
                    "SpotFleet{}".format(
                        sanitize_cfn_resource_name(
                            spot_fleet.get('name')
                        )
                    )
                ),
                "STATUS": Sub("${Status}"),
                "VERSION": Sub("${Version}"),
                "SCALE_IN_THRESHOLD": Sub("${SpotTaskThresholdIn}"),
                "SCALE_OUT_THRESHOLD": Sub("${SpotTaskThresholdOut}"),
                "MAX_WEIGHT": Sub("${SpotMaxWeight}"),
                "MIN_WEIGHT": Sub("${SpotMinWeight}")
            }
        ),
        Timeout=900,
        MemorySize=128,
        Runtime="python3.7",
    )
    template.add_resource(scaling_lambda)
    CronScaling = Rule(
        "CronScaling{}".format(
            sanitize_cfn_resource_name(spot_fleet.get('name'))
        ),
        ScheduleExpression="rate(1 minute)",
        Description="Cron for cluster stats",
        Targets=[
            Target(
                Id="1",
                Arn=GetAtt(scaling_lambda, "Arn"))
        ]
    )
    template.add_resource(CronScaling)
    ScalingPerm = Permission(
        "ScalePerm{}".format(
            sanitize_cfn_resource_name(spot_fleet.get('name'))
        ),
        Action="lambda:InvokeFunction",
        FunctionName=GetAtt(scaling_lambda, "Arn"),
        Principal="events.amazonaws.com",
        SourceArn=GetAtt(CronScaling, "Arn")
    )
    template.add_resource(ScalingPerm)
