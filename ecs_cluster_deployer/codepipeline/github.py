'''
Class for setting github hooks into codepipeline
'''
import boto3
import botocore #pylint: disable=unused-import
from troposphere.codepipeline import Webhook, WebhookAuthConfiguration, WebhookFilterRule
from troposphere import Ref, GetAtt

class GithubSecret():
    '''
    This class will allow folks to use github saas to hook up their code pipelines
    '''
    def __init__(self):
        self.sm = boto3.client('secretsmanager') #pylint: disable=C0103


    def check_github_secret(self, sm_secret_name='GithubToken', kms_key=None):
        ''' Takes in a Secrets Manager secret name and will ask for input if it fails '''
        secrets = list(self.find_github_secret(sm_secret_name))
        if not secrets:
            print(f"Can't find the secret {sm_secret_name} secret in secrets manager...")
            yes_i_would = input("Would you like to add one now? y/N")
            if yes_i_would.lower() in ['y', 'Yes', 'yes']:
                self.create_github_secret(sm_secret_name, kms_key)
            else:
                print('Exiting everything...')

    def create_github_secret(self, secret_name, kms_key):
        '''
        This method will allow users to input the secret for their PAT token
        if they don't have one stored in secrets manager in AWS
        '''
        print('Creating secrets manager github secret')
        secret = input('Please Enter Github Personal Access Token for Codepipeline: ')
        my_args = {
            'Name': secret_name,
            'Description': 'Github oauth personal access token for CI/CD',
            'SecretString': secret
        }
        if kms_key:
            my_args['KmsKeyId'] = kms_key

        res = self.sm.create_secret(**my_args)
        print(res)

    def find_github_secret(self, secret_name):
        '''
        Searches for your github secret in secrets manager
        '''
        pager = self.sm.get_paginator("list_secrets")
        iterator = pager.paginate()
        for page in iterator:
            secrets = page["SecretList"]
            for secret in secrets:
                if secret['Name'] == secret_name:
                    yield secret

    @staticmethod
    def add_webhook(t): #pylint: disable=C0103
        '''
        This will add the webhook resource to a codepipeline in order to listen
        for events from github
        '''
        git_hook = Webhook(
            "GitHook",
            Authentication='GITHUB_HMAC',
            AuthenticationConfiguration=WebhookAuthConfiguration(
                SecretToken="{{resolve:secretsmanager:GithubToken:SecretString}}"
            ),
            Filters=[WebhookFilterRule(
                JsonPath="$.ref",
                MatchEquals="refs/heads/{Branch}"
            )],
            TargetPipeline=Ref("AppPipeline"),
            TargetPipelineVersion=GetAtt("AppPipeline", "Version"),
            TargetAction='SourceAction',
            RegisterWithThirdParty="true"
        )

        t.add_resource(git_hook)
