'''
This is going to be simple.

Pull ssm datetime.
If difference(datetime, now) > scale_cooldown || error:
    if schedulabletasks > threshold_in
        scalein()
        $?
        ssm_date_set()
    if schedulabletasks < threshold_out
        scaleout()
        $?
        ssm_date_set()

Env vars:
- CLUSTER_NAME
- THRESHOLD_IN
- THRESHOLD_OUT
- SCALE_COOLDOWN
-

'''
from datetime import datetime, timedelta
import logging
import json
import os
import boto3
import botocore

logger = logging.getLogger()
logging.basicConfig()
logger.setLevel(logging.INFO)

class SpotScaler: #pylint: disable=R0902
    """
    This will scale the spot fleet based on a custom assignment of our
    cloudwatch metrics
    """
    def __init__(self):
        self.ssm = boto3.client('ssm')
        self.cw = boto3.client('cloudwatch')
        self.ec2 = boto3.client('ec2')
        self.ecs = boto3.client('ecs')
        self.cfn = boto3.client('cloudformation')
        self.lambdy = boto3.client('lambda')
        self.threshold_in = os.environ.get('SCALE_IN_THRESHOLD', 7)
        self.threshold_out = os.environ.get('SCALE_OUT_THRESHOLD', 2)
        self.scale_cooldown = os.environ.get('SCALE_COOLDOWN', 300)
        self.scale_amount_down = os.environ.get('SCALE_IN_AMOUNT', 1)
        self.scale_amount_up = os.environ.get('SCALE_OUT_AMOUNT', 2)
        self.min_weight = int(os.environ.get('MIN_WEIGHT', '1'))
        self.max_weight = int(os.environ.get('MAX_WEIGHT', '10'))
        self.scale_metric = os.environ.get('SCALE_METRIC', 'Schedulable Cluster Tasks')
        self.enabled = self.str2bool(os.environ.get('ENABLED', 'TRUE'))
        self.spot_fleet = os.environ.get('SPOT_FLEET')
        self.cluster_name = os.environ.get('CLUSTER_NAME')
        self.version = os.environ.get('VERSION')
        self.ssm_path = '/ecs-maestro/{}/{}/scaletime'.format(self.cluster_name, self.version)
        self.deactivate = os.environ.get('STATUS', 'active') == 'inactive'

    def last_scale_date(self):
        """ Gets the last scale date from SSM """
        try:
            res = self.ssm.get_parameters(
                Names=[self.ssm_path]
            )
            return datetime.strptime(
                res['Parameters'][0]['Value'],
                "%Y-%m-%d %H:%M:%S.%f"
            )
        except botocore.exceptions.ClientError:
            return datetime.utcnow() - timedelta(minutes=2)
        except ValueError:
            return datetime.utcnow() - timedelta(minutes=2)

    @staticmethod
    def str2bool(v):
        """ cleans env vars """
        return v.lower() in ("yes", "true", "t", "1")

    def set_date(self):
        """ Sets date to ssm """
        try:
            self.ssm.delete_parameter(
                Name=self.ssm_path
            )
        except botocore.exceptions.ClientError:
            logger.info("Couldn't delete %s", self.ssm_path)

        self.ssm.put_parameter(
            Name=self.ssm_path,
            Value=self.cooldown_time(),
            Overwrite=True,
            Type='String'
        )

    def deactivate_stack(self):
        '''
        scale_in_asg()
        scale_in_spot()
        query_ecs = drain_undrained_by_version()
        delete_stack()
        '''
        logger.info('deactivate stack')
        if self.last_scale_date() > datetime.utcnow():
            logger.info("Last scale date: %s", str(self.last_scale_date()))
            return
        # if self.drain_asg():
        #     self.set_date()
        #     return
        if self.drain_spot():
            logger.info('Draining spot fleet...')
            self.set_date()
            return

        if self.cluster_version_empty():
            logger.info('No more instances with this version')
            self.delete_stack()
            logger.info("Delete the stack----")

    def cluster_version_empty(self):
        """ Returns if this version of the cluster no longer has instances """
        instances = self.ecs.list_container_instances(
            cluster=self.cluster_name,
            filter='attribute:asg_version == {}'.format(self.version),
            status='ACTIVE'
        ).get('containerInstanceArns', [])
        return len(instances) == 0

    def delete_stack(self):
        """ Delete the cloudformation stack by kicking off lambda """
        def sanitize_cfn_resource_name(name):
            name = ''.join([n.title() for n in name.split('-')])
            return name
        lambda_name = sanitize_cfn_resource_name(os.environ.get('CLUSTER_NAME'))
        stack_name = f"{self.cluster_name}-asg-{self.version}"
        res = self.lambdy.invoke(
            FunctionName=f"{lambda_name}ASGCleanupLambda",
            Payload=json.dumps({
                "asg_stack": stack_name
            })
        )
        logger.info(res)
        logger.info("Removed stack %s", stack_name)

    # def drain_asg(self):
    #     """ This function will drain the ASG """
    #     logger.info('Draining asg...NOT IMPLEMENTED')


    def drain_spot(self):
        """ Modify the spot fleet """
        target_cap = self.ec2.describe_spot_fleet_requests(
            SpotFleetRequestIds=[self.spot_fleet]
        )['SpotFleetRequestConfigs'][0]['SpotFleetRequestConfig']['TargetCapacity']
        logger.info(target_cap)
        if target_cap > 0:
            self.ec2.modify_spot_fleet_request(
                SpotFleetRequestId=self.spot_fleet,
                TargetCapacity=target_cap - self.scale_amount_down
            )
            return True
        return False

    def scale_spot(self, amount):
        """ Scale the spot fleet out """
        current_target_size = self.ec2.describe_spot_fleet_requests(
            SpotFleetRequestIds=[self.spot_fleet]
        )['SpotFleetRequestConfigs'][0]['SpotFleetRequestConfig']['TargetCapacity']

        new_target_size = current_target_size + amount

        if new_target_size < self.min_weight:
            new_target_size = self.min_weight

        if new_target_size > self.max_weight:
            new_target_size = self.max_weight

        if new_target_size == current_target_size:
            logger.info('Not scaling because target size is at the min / max.')
            return

        if self.has_running_tasks() and new_target_size == 0:
            logger.info('Not scaling because this cluster still has tasks')
            return

        try:
            self.ec2.modify_spot_fleet_request(
                SpotFleetRequestId=self.spot_fleet,
                TargetCapacity=new_target_size
            )
            logger.info("TargetCapacity: %s", str(current_target_size))
            logger.info("Scaling spot fleet by %s", str(amount))
            logger.info("Adding the two: %s", str(current_target_size + amount))
        except botocore.exceptions.ClientError:
            logger.error('failed to modify spot instances')

    def scale(self, amount):
        """ Scales the spot fleet but checks the date first """
        logger.info("Will scale again after: %s", str(self.last_scale_date()))
        if self.last_scale_date() > datetime.utcnow():
            logger.info("Cooldown in effect...")
            return
        self.scale_spot(amount)
        self.set_date()
        logger.info("Set the new time")

    def get_metric(self):
        """ Get our average scale metric statistics for the cluster  """
        res = self.cw.get_metric_statistics(
            Namespace='AWS/ECS',
            Period=4*60,
            MetricName=self.scale_metric,
            StartTime=(
                datetime.now() - timedelta(minutes=4)
            ),
            EndTime=datetime.now(),
            Dimensions=[{'Name': 'ClusterName', 'Value': self.cluster_name}],
            Statistics=['Average']
        )
        logger.info(res)
        return res['Datapoints'][0]['Average']

    def has_running_tasks(self):
        """ checks to see if the cluster has running tasks """
        res = self.ecs.list_tasks(
            cluster=self.cluster_name,
            desiredStatus='RUNNING'
        )
        logger.info(res)
        return len(res['taskArns']) > 0

    def cooldown_time(self):
        """ Calculates cooldown time of the cluster scale events """
        return str(timedelta(seconds=self.scale_cooldown) + datetime.utcnow())


def lambda_handler(event, context): #pylint: disable=W0613
    """ lambda init """
    spot_scaler = SpotScaler()
    if spot_scaler.deactivate:
        spot_scaler.deactivate_stack()
        return
    if spot_scaler.enabled:
        metric = spot_scaler.get_metric()
        logger.info("Metric: %s", str(metric))
        if metric > float(spot_scaler.threshold_in):
            spot_scaler.scale(-int(spot_scaler.scale_amount_down))
            logger.info('Scaling down %s', str(spot_scaler.scale_amount_down))
        if metric < float(spot_scaler.threshold_out):
            spot_scaler.scale(int(spot_scaler.scale_amount_up))
            logger.info('Scaling up %s', str(spot_scaler.scale_amount_up))
    else:
        logging.info('Scaling not enabled.')
