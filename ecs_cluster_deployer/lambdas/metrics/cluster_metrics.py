"""

Cluster Metrics
These metrics are used to scale the cluster and provide insight into all the
resources that the cluster is using.

"""

import os
import logging
import datetime
import boto3
import dateutil

logger = logging.getLogger()
logging.basicConfig()
logger.setLevel(logging.INFO)

def lambda_handler(event, context): #pylint: disable=W0613
    """
    This lambda handler handles cluster analytics.

    These are used for scaling the cluster and watching memory / cpu requirements.
    """
    agg = ClusterStats(os.environ['CLUSTER'])
    agg.send_cluster_metrics()

class ContainerStats:
    """
    Holds container based statistics
    """
    def __init__(self, container):
        self._container = container

    @property
    def name(self):
        """ returns the container name """
        return self._container['name']

    @property
    def cpu(self):
        """ returns cpu """
        return self._container['cpu']

    @property
    def memory(self):
        """ returns which is greater, memory or memory reservation """
        return int(
            max(
                self._container.get('memory', 0),
                self._container.get('memoryReservation', 0)
            )
        )

class ServiceStats:
    """ Object for service stats """
    def __init__(self, service):
        self._svc = service
        self.task_definition = service["taskDefinition"]
        self._task_definitions = []
        self.desired = service["desiredCount"]
        self.ecs = boto3.client('ecs')

    @property
    def cpu_per_pod(self):
        """ Sums the total cpu in the pod """
        return sum(
            (container.cpu for container in self.containers)
        )
    @property
    def cpu_requirement(self):
        """ required cpu needed for the service to run properly """
        return self.cpu_per_pod * self.desired

    @property
    def memory_per_pod(self):
        """ returns total memory of the pod """
        return sum(
            (container.memory for container in self.containers)
        )

    @property
    def memory_requirement(self):
        """ returns memory needed for the service to run on the cluster """
        return self.memory_per_pod * self.desired

    @property
    def containers(self):
        """ Set the container definitions """
        if not self._task_definitions:
            self._task_definitions = self.ecs.describe_task_definition(
                taskDefinition=self.task_definition
            )['taskDefinition']['containerDefinitions']
        return [ContainerStats(container) for container in self._task_definitions]

    @property
    def running(self):
        """ get the number of running pods in the service """
        return self._svc['runningCount'] + self._svc['pendingCount']

class ContainerInstanceStats:
    """ class for container instance statistics """
    def __init__(self, container_instance):
        self._ci = container_instance

    @property
    def available_cpu(self):
        """ Return the available cpu of the container instance """
        return [
            item["integerValue"] \
            for item in self._ci["remainingResources"] if item["name"] == "CPU"
        ][0]

    @property
    def total_cpu(self):
        """ returns the nodes total cpu - this is the amount that it has minus daemons """
        return [
            item["integerValue"] \
            for item in self._ci["registeredResources"] if item["name"] == "CPU"
        ][0]

    @property
    def available_memory(self):
        """ returns the total available memory of the container instance """
        return [
            item["integerValue"] \
            for item in self._ci["remainingResources"] if item["name"] == "MEMORY"
        ][0]

    @property
    def total_memory(self):
        """  returns total memory of the node minus daemon sets """
        return [
            item["integerValue"] \
            for item in self._ci["registeredResources"] if item["name"] == "MEMORY"
        ][0]


class ClusterStats():
    """
    Cluster stats object that sets up the information needed to pass to cloudwatch
    """
    def __init__(self, cluster_name):
        self._container_instances = []
        self._services = []
        self.ecs = boto3.client('ecs')
        self.cw = boto3.client('cloudwatch')
        self.cluster_name = cluster_name


    @property
    def services(self):
        """ returns services for the cluster """
        if not self._services:
            self._services = list(self._resolve_ecs_services())
        return self._services

    @property
    def active_services(self):
        """ returns services that are desired, not if services re inactive """
        return list(filter(None, [service for service in self.services if service.desired > 0]))

    @property
    def service_requirements(self):
        """ returns all the services requirements for memory and cpu """
        return  {
            'cpu': sum((service.cpu_requirement for service in self.active_services)),
            'memory': sum((service.memory_requirement for service in self.active_services)),
        }

    @property
    def desired_pods(self):
        """ returns total desired pods """
        return sum((service.desired for service in self.active_services))

    @property
    def largest_pod(self):
        """
        returns largest memory pod in cluster
        if we can't schedule these, we need to scale
        """
        try:
            return list(
                reversed(
                    sorted(
                        self.active_services,
                        key=lambda svc: svc.memory_per_pod
                    )
                )
            )[0]
        except IndexError:
            return None

    @property
    def cluster_pod_dimensions(self):
        """
        returns:
            total_number_spaces
            percentage_occupied
        """
        if self.largest_pod:
            total_spaces = 0
            for ci in self.container_instances:
                # gather available spaces in cpu and memory
                try:
                    cpu_spaces = ci.available_cpu / self.largest_pod.cpu_per_pod
                except:
                    cpu_spaces = ci.available_cpu
                try:
                    mem_spaces = ci.available_memory / self.largest_pod.memory_per_pod
                except:
                    mem_spaces = ci.available_memory
                instance_spaces = min(cpu_spaces, mem_spaces)
                total_spaces += instance_spaces

            return total_spaces, float(self.desired_pods) / (self.desired_pods + total_spaces)

        logger.info("No active services on this cluster")
        return 999999, 0

    @property
    def container_instances(self):
        """ returns container instances for the cluster """
        if not self._container_instances:
            self._container_instances = self._list_container_instances()
        return self._container_instances

    @property
    def available_memory(self):
        """ returns total cluster memory available """
        return sum([ci.available_memory for ci in self.container_instances])

    @property
    def total_memory(self):
        """ return total memory of cluster """
        return sum([ci.total_memory for ci in self.container_instances])

    @property
    def available_cpu(self):
        """ returns cpu that is left after daemonsets """
        return sum([ci.available_cpu for ci in self.container_instances])

    @property
    def total_cpu(self):
        """ returns total cpu of the cluster """
        return sum([ci.total_cpu for ci in self.container_instances])

    def send_cluster_metrics(self):
        """
        This method collects the container instances and gets all the service
        information. It then calculates the usage info from those services.
        It will then write that metric data to CloudWatch.
        """
        cluster_dimensions = self.cluster_pod_dimensions
        self.cw.put_metric_data(
            Namespace='AWS/ECS',
            MetricData=[{
                "MetricName": "Schedulable Cluster Tasks",
                "Dimensions": [{
                    "Name": "ClusterName",
                    "Value": self.cluster_name
                }],
                "Timestamp": datetime.datetime.now(dateutil.tz.tzlocal()),
                "Value": cluster_dimensions[0]
            }, {
                "MetricName": "Scheduled Percentage",
                "Dimensions": [{
                    "Name": "ClusterName",
                    "Value": self.cluster_name
                }],
                "Timestamp": datetime.datetime.now(dateutil.tz.tzlocal()),
                "Value": cluster_dimensions[1]
            }]
        )

    def _list_container_instances(self):
        container_instance_arns = []
        container_instances = []
        pager = self.ecs.get_paginator("list_container_instances")
        iterator = pager.paginate(
            cluster=self.cluster_name,
            status='ACTIVE'
        )
        for page in iterator:
            container_instance_arns.extend(page["containerInstanceArns"])

        for arns in self._chunk(container_instance_arns, 50):
            res = self.ecs.describe_container_instances(
                cluster=self.cluster_name,
                containerInstances=arns
            )
            for container_instance in res.get('containerInstances'):
                container_instances.append(container_instance)

        return [
            ContainerInstanceStats(container_instance) \
            for container_instance in container_instances
        ]

    @staticmethod
    def _chunk(l, n):
        for i in range(0, len(l), n):
            yield l[i:i + n]

    def _get_service_arns(self):
        pager = self.ecs.get_paginator("list_services")
        iterator = pager.paginate(cluster=self.cluster_name, PaginationConfig={'PageSize': 10})
        for page in iterator:
            arns = page["serviceArns"]
            for arn in arns:
                yield arn

    def _resolve_ecs_services(self):
        service_arns = list(self._get_service_arns())
        for batch in self._chunk(service_arns, 10):
            services = self.ecs.describe_services(cluster=self.cluster_name, services=batch)['services']
            for service in services:
                yield ServiceStats(service)
