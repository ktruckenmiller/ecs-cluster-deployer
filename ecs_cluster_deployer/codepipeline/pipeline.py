'''
These methods will construct an ECS Cluster Deployer git based codepipeline
'''
import os

from troposphere import Sub, GetAtt
from troposphere.codepipeline import (
    Pipeline,
    Stages,
    Actions,
    ActionTypeId,
    OutputArtifacts,
    InputArtifacts,
    ArtifactStore,
)
from git import Repo #pylint: disable=E0401
from ecs_cluster_deployer.utils import sanitize_cfn_resource_name

class GitHubNotFound(Exception):
    ''' Custome exception for github errors '''


def get_branch():
    '''
    This will gather your current branch using your git directory
    '''
    repo = Repo(os.getcwd())
    branch = repo.active_branch
    return branch.name

def get_repository_and_owner():
    '''
    This will get your repository name and the organization owner.

    returns repo, owner
    '''
    repo = Repo(os.getcwd())
    remote = repo.git.remote("get-url", "--all", "origin")
    if 'https://github.com' in remote:
        # 'https://github.com/ktruckenmiller/jabba-the-hut.git'
        repo_arr = remote.split('https://github.com')[1].split('.git')[0].split('/')
        return repo_arr[1], repo_arr[2]
    if 'git@github' in remote:
        owner = remote.split(':')[1].split('.git')[0].split("/")[0]
        repository = remote.split(':')[1].split('.git')[0].split("/")[1]
        return owner, repository
    raise GitHubNotFound("Couldn't find a repo owner or organization in your repo")

def add_pipeline(t, environments, name):
    '''
    This will add a codepipeline that deploys the ecs clusters.
    '''
    name = sanitize_cfn_resource_name(name)
    app_stages = []
    branch = get_branch()
    owner, repository = get_repository_and_owner()
    # Add Source Stage
    app_stages.append(Stages(
        Name="Source",
        Actions=[
            Actions(
                Name="SourceAction",
                ActionTypeId=ActionTypeId(
                    Category="Source",
                    Owner="ThirdParty",
                    Version="1",
                    Provider="GitHub"
                ),
                OutputArtifacts=[
                    OutputArtifacts(
                        Name="SourceOutput"
                    )
                ],
                Configuration={
                    "Owner": owner,
                    "Repo": repository,
                    "OAuthToken": "{{resolve:secretsmanager:GithubToken:SecretString}}",
                    "PollForSourceChanges": 'false',
                    "Branch": branch
                },
                RunOrder="1"
            )
        ]
    ))

    # Add AMI stage
    app_stages.append(Stages(
        Name="BuildAMI",
        Actions=[
            Actions(
                Name="AMIBuilder",
                InputArtifacts=[
                    InputArtifacts(
                        Name="SourceOutput"
                    )
                ],
                ActionTypeId=ActionTypeId(
                    Category="Build",
                    Owner="AWS",
                    Version="1",
                    Provider="CodeBuild"
                ),
                Configuration={
                    "ProjectName": {"Ref": "PackerAMIBuilder"}
                },
                OutputArtifacts=[
                    OutputArtifacts(
                        Name='AMI'
                    )
                ],
                RunOrder="1"
            )
        ]
    ))

    for environment in environments:
        # Now add the environments
        app_stages.append(Stages(
            Name=f"Deploy{environment.title()}",
            Actions=[
                Actions(
                    Name=f"Deploy{name}{environment.title()}",
                    InputArtifacts=[
                        InputArtifacts(
                            Name="AMI"
                        )
                    ],
                    ActionTypeId=ActionTypeId(
                        Category="Build",
                        Owner="AWS",
                        Version="1",
                        Provider="CodeBuild"
                    ),
                    Configuration={
                        "ProjectName": {"Ref": f"Deploy{name}{environment.title()}"}
                    },
                    RunOrder="1"
                )
            ]
        ))

    t.add_resource(Pipeline(
        "AppPipeline",
        DependsOn="PackerInstanceProfile",
        RoleArn=GetAtt("PipelineRole", "Arn"),
        Stages=app_stages,
        ArtifactStore=ArtifactStore(
            Type="S3",
            Location=Sub("ecs-cluster-deployer-${AWS::AccountId}-${AWS::Region}")
        )
    ))
