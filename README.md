# ecs-cluster-deployer
[![Build Status](https://drone.kloudcover.com/api/badges/ktruckenmiller/ecs-cluster-deployer/status.svg)](https://drone.kloudcover.com/ktruckenmiller/ecs-cluster-deployer)

## Pre-requisites

- Docker

## Developer

For more configurations options and technical documentation, please visit the docs at [DEVELOPER.md](DEVELOPER.md)

## TL;DR;
Create a file called `infra.yml` and paste in the following for a small cluster:
```yaml
---
  # basic example
kind: aws-ecs-cluster-deployer
cluster:
  name: my-test-cluster
ec2_instances:
  autoscaling: true
  ebs_mounts:
    - name: basic
      device_name: /dev/xvda
      size: 20
  spot_fleets:
    - name: main
      desired_weight: 1
      min_weight: 0
      max_weight: 16
      bids:
        - instance_type: t3.small
          price: 0.01
        - instance_type: t3.medium
          price: 0.014
```

Then run the following:

```bash
# If you want to use your base credentials for AWS in a directory
docker run -it --rm \
  -v $(pwd):$(pwd) \
  --workdir=$(pwd)\
  -e AWS_DEFAULT_REGION=us-east-2 \
  -e VERSION=$(git rev-parse HEAD) \
  -v ~/.aws/credentials:/root/.aws/credentials:ro \ # read only
  ktruckenmiller/ecs-cluster-deployer put-pipeline
```

```bash
# If you are running Docker Friend with AWS MFA and you're security conscious
# https://github.com/ktruckenmiller/docker-friend
docker run -it --rm \
  -v $(pwd):$(pwd) \
  --workdir=$(pwd)\
  -e AWS_DEFAULT_REGION=us-east-2 \
  -e VERSION=$(git rev-parse HEAD) \
  -e IAM_ROLE=<your Docker Friend deployment AWS role ARN> \
  ktruckenmiller/ecs-cluster-deployer put-pipeline
```



## Reasoning

Typically designing and deploying an ECS fleet can be difficult if you don't know all the ins-and-outs of autoscaling groups, spot fleets, scaling, and container management. This repository aims to provide the user with a simple way to not have to focus on the nitty gritty of deployment, and focus on using the control plane of ECS like you would Fargate.

AWS does a lot of things really well. The only issue I have with AWS is that they don't make things as simple as possible. They try to make them as extensible and unchanging as possible. Which is great for engineers like me. But sometimes I don't want to engineer things if I'd rather focus on the application layer and not the deployment layer. That's what this is for.

### Why Not Deploy My Own EC2 Fleets?

At all costs, you want to avoid managing raw linux compute environments. This is for a couple reasons, but mostly:

- the cycle time is lengthy
- patches and new updates require redeployment
- configuration matrix is vast
- knowledge of resources used

### Why Not Use Fargate?

Fargate is adding functionality at a rapid rate, but it still doesn't have a great answer for:

- EBS volume support
- ~~EFS volume support~~
- Docker socket access
- SSH access for troubleshooting
- Cold start time with cached images
- Memory limit (30gb)
- Storage size limit (10gb)
- Max docker image size above (4gb)

### Straight Up Cheaper

#### Cost Comparison

Cost comparison with spot is slightly variable depending on the CPU/Memory requirements, but as of today, I will compare costs in the `us-west-2` region.

| Type | Cost per Hour | CPU | Memory |
| ---- | ------------- | --- | ------ |
| Fargate | $0.04937 | `1 vcpu` | `2gb` |
| ECS Spot Fleet | $0.0063 | `1 vcpu` | `2gb` |
| Fargate | $0.295 | `4 vcpu` | `30gb` |
| ECS Spot Fleet | $0.0418 | `4 vcpu` | `32gb` |

| Type | Cost per Month | CPU | Memory |
| ---- | ------------- | --- | ------ |
| Fargate | $36.73 | `1 vcpu` | `2gb` |
| ECS Spot Fleet | $4.69 | `1 vcpu` | `2gb` |
| Fargate | $219.48 | `4 vcpu` | `30gb` |
| ECS Spot Fleet | $31.10 | `4 vcpu` | `32gb` |

### What Does This Tool Actually Do?

There are many headaches that this repo tries to solve. Currently the following are the primary objectives.

#### Deployment

Using AWS CodePipeline we can make sure that deployability matches the AWS experience. This project makes it easy to deploy a CodePipeline that can deploy your new ECS fleets by running `put-pipeline`. This allows you to not have to worry about Jenkins or another type of deployment framework outside of AWS because it runs builds and deploys in a simple and extensible pipeline.

If you use github for source control, you're in luck. This integrates directly with github, all you need to do is input a Personal Access Token (PAT) per environment. This will store this token in AWS Secrets Manager so that the pipeline has access to this secret during runtime, and additionally you can use this same `Source` configurations in other CodePipeline projects.

If you want to run a multi-region ECS Fleet, you can simply run a `put-pipeline` in another region, giving you ultimate automation across multiple regions to keep your deploys in sync from source control. They will all run when source control changes.

#### AMI

Using the ECS optimized AMI is great for running ECS. This AMI also comes with extra libraries needed for running ECS. In addition, if it has already built an AMI, it will tag this AMI and not rebuild it if the upstream AMI hasn't changed. You can always rebuild but untagging the AMI.

#### Auto Scaling

Scaling is built in from both the fleet perspective, and the task perspective. If there is no room for more tasks, it will scale out the cluster. If there is too much capacity, it will scale in the cluster. This cluster will make sure and drain your instances if they are running containers so that they are rescheduled on other hosts if they get pushed off.

Don't have anything running on the cluster? It will scale to zero.

#### Smoke Test

In order to make sure that your cluster is working properly, a smoke test is performed on the new cluster to make sure that things are functioning as normal. If there is a failure of ECS to run tasks normally, the test will fail it will scale in the new fleet to zero. Further deploys will clean up this failed cluster without downtime.

#### EC2 ASG

Want to run an autoscaling group? You can do that as well if you have reserved instances that you've already purchased. Put them in an autoscaling group in the config and it will be added to your fleets.

#### Mounts

You can add EFS mounts if needed, and additionally control the EBS volume size that is attached to your instances.

#### Clean Up

When a new cluster comes online, the old cluster is marked as inactive if a successful deploy has been completed. This is all done for you, no need for the user to be involved with gray clusters.

### What Does This Tool Not Do?

This tool doesn't support these things yet:

- multiple spot fleets per deploy
- source control other than GitHub
