"""
This function will remove the stack from the event that has been sent.
"""
import logging
import boto3

logger = logging.getLogger()
logging.basicConfig()
logger.setLevel(logging.INFO)

def lambda_handler(event, context): #pylint: disable=W0613
    """
    Lambda handler
    """
    logger.info(event)
    cf = boto3.client('cloudformation')
    res = cf.delete_stack(
        StackName=event['asg_stack']
    )
    logger.info(res)
