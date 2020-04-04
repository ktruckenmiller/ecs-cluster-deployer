"""
CloudFormation deployer
"""
import logging
import time
import sys
import os
import subprocess
import boto3
import botocore

logger = logging.getLogger()
logging.basicConfig()
logger.setLevel(logging.INFO)

class Runner:
    """ Deploys CloudFormation Stacks for us """
    def __init__(self):
        self.cf = boto3.client('cloudformation', region_name=os.environ['AWS_DEFAULT_REGION'])
        self.stack_name = ""

    @property
    def version(self):
        """ The version of the deployment """
        if os.environ.get('VERSION'):
            return os.environ.get('VERSION')
        return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode(sys.stdout.encoding).strip()

    def get_stack_errors(self):
        """ Displays stack errors for the user """
        res = self.cf.describe_stack_events(
            StackName=self.stack_name)
        error = ""
        for event in res['StackEvents']:
            if event.get('ResourceStatusReason') == 'Resource update cancelled':
                error = 'Resource update cancelled'
                break
            if len(error) < len(event.get('ResourceStatusReason', '')):
                error = event.get('ResourceStatusReason')
        return error

    def in_progress(self):
        """
        1. check if the stack name is updating
        2. if it is, check the git-version. If its the same version, return true
        """
        IN_PROGRESS = ["UPDATE_IN_PROGRESS", "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS", "CREATE_IN_PROGRESS"]
        try:
            res = self.cf.describe_stacks(StackName=self.stack_name)['Stacks'][0]
            current_stack_version = [tag["Value"] for tag in res['Tags'] if tag["Key"] == "version"][0]
            if res["StackStatus"] in IN_PROGRESS and current_stack_version == self.version:
                return True
        except IndexError as err:
            return False
        except botocore.exceptions.ClientError as err:
            logger.error(err)
        return False

    def stack_exists(self):
        """
        cloudformation doesn't have a built in function in boto for this
        """
        try:
            res = self.cf.describe_stacks(StackName=self.stack_name)
            logger.info(res)
            return True
        except IndexError:
            return False
        except botocore.exceptions.ClientError as err:
            if err.response['Error'][ #pylint: disable=R1705
                    'Message'] == 'Stack with id {} does not exist'.format(
                        self.stack_name):
                return False
            else:
                raise


    def wait_on_stack(self, stack_action):
        """ Sit here and wait on the stack to see if it succeeds """
        counter = 1
        for _ in range(counter, 240, 1):
            stack_status = self.cf.describe_stacks(
                StackName=self.stack_name)['Stacks'][0]['StackStatus']

            if stack_status == '{}_IN_PROGRESS'.format(
                    stack_action.upper()):
                time.sleep(30)
                logger.info("Waiting on CloudFormation...")

            elif stack_status == 'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS':
                time.sleep(30)
                logger.info("Almost done, Cleaning up.")

            elif stack_status == '{}_COMPLETE'.format(
                    stack_action.upper()):
                logger.info("StackComplete")
                return True
            else:
                stack_errors = self.get_stack_errors()
                logger.error(stack_errors)
                raise Exception("Deploy failed: {}.".format(
                    stack_status))
        logger.error("Stack timed out. :(")
        logger.error(stack_action)
        return False

    def push_cloudformation(self, template):
        """ Create / Update the CloudFormation Stack """
        stacks = None
        try:
            res = self.cf.describe_stacks(
                StackName=self.stack_name
            )
            stacks = res.get("Stacks")
        except botocore.exceptions.ClientError as err:
            if 'does not exist' not in err.response['Error'][
                    'Message']:
                raise

        if stacks:
            action = 'UPDATE'
            try:

                res = self.cf.update_stack(
                    StackName=self.stack_name,
                    TemplateBody=template.to_json(),
                    Parameters=[{
                        "ParameterKey": "Version",
                        "ParameterValue": self.version,
                        "UsePreviousValue": False,
                    }],
                    Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
                )
                # self.state_id = res['Stacks'][0]['StackId']
                self.wait_on_stack(action)
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Message'] == 'No updates are to be performed.':
                    logger.info('no update')
                else:
                    raise

        else:

            action = 'CREATE'
            res = self.cf.create_stack(
                StackName=self.stack_name,
                TemplateBody=template.to_json(),
                Parameters=[{
                    "ParameterKey": "Version",
                    "ParameterValue": self.version,
                    "UsePreviousValue": False,
                }],
                Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'],
                OnFailure='DELETE'
            )
            self.wait_on_stack(action)
