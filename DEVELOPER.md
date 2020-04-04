# Development

ECS Cluster Deployer does everything with Docker. If you don't use Docker, that's ok. It's an easy way to package and distribute applications.

## How to test

### Unit Tests

Right now, unit tests are performed by running `make unit`.

### Testing Cluster Deploy

Todo - right now I'm just pushing out staging-kloudcover.

## Releases

You can commit to master to cut a new version, and test that version.

To release a new version, `git tag 0.x.x`, and then `git push origin --tags`.


## Container Environment Variables

You can provide environment variables at the docker container run in order to pass these into the container as flags. These will change the operating capability on a global level.

| environment variable | description | required | default |
| -------------------- | ----------- | -------- | ------- |
| `AWS_DEFAULT_REGION` | region cluster and pipeline would be deployed to | No | `us-west-2` |
| `VALUES_FILE` | the `infra.yml` file may not be the same for each environment, you can set it here | No | `infra.yml` |
| `VERSION` | the version of the cluser, it should be different for each deploy | No | `git rev-parse HEAD` |

## Definition
### infra.yml Base Vars
| root var | description | required | type | default |
|----      | ----        | ---      | ---- | ------- |
| `cluster` | cluster definition object | True | dict |  |
| `ec2_instances` | ec2_instances definition object | True | dict |  | |


### Cluster Base Vars
```yaml
# example
cluster:
  name: dev-cluster
  vpc: vpc-88888888
  availability_zones:
    - us-west-2a
    - us-west-2c
    - us-west-2b
  subnets:
    - subnet-9b2938c2
    - subnet-9b2938c3
    - subnet-9b2938c4
  security_groups:
    - sg-093c234a
  security_group_ingress:
    - sg-dab3aca
```

| root var | description | required | type | default |
|-|-|-|-|-|
| `name`      | the name of your cluster| Yes | string |  | |
| `vpc` | the specific vpc you'd like to deploy to | No | `vpc id` | default vpc |
| `availability_zones` | the availability zones you'd like to use for your cluster instances | No | available zones for the region | default vpc availability zones |
| `subnets` | the subnets you'd like to use for each availability zone | No | subnet ids | default vpc subnets |
| `security_groups` | the security groups you'd like to apply to the nodes on the ecs cluster | No | security group ids | create default security group for the cluster nodes |
| `security_group_ingress` | the security group you'd like to be allowed to communicate with the nodes of the ecs cluster, the cluster nodes will allow this as an ingress | No | security group id | None |

### EC2 Instances Base Vars

```yaml
# example with all options
instance_profile_arn: arn:aws:iam::${AWS::AccountId}:instance-profile/ecsInstanceRole
autoscaling: true
efs_mounts:
  - name: kloudcover-mount
    efs_id: fs-df827476
    local_path: /efs

ebs_mounts:
  - name: basic
    device_name: /dev/xvda
    size: 20

auto_scaling_groups:
  - name: reserved
    instance_type: t2.medium
    desired_instances: 1

spot_fleets:
  - name: main
    timeout: 3m
    desired_weight: 1
    min_weight: 0
    max_weight: 16
    bids:
      - instance_type: t3.medium
        price: 0.015
      - instance_type: t3.small
        price: 0.01
      - instance_type: t3.medium
        price: 0.014

```


| root var | description | required | type | default |
| - | - | - | - | - |
| `instance_profile_arn` | instance profile that the ECS EC2 nodes will apply to themselves | No | string | base instance profile that allows for SSM sessions and ECS roles to be passed to tasks |
| `autoscaling` | bool if you'd like the cluster to autoscale when it can't schedule tasks | no | bool | true |
| `efs_mounts` | EFS mounts that you'd like to add to the cluster | no |  `list` of [efs dicts](#EFS-Mount-Dict) | |
| `ebs_mounts` | EBS mounts that you'd like to add to the cluster nodes | no | `list` of [ebs dicts](#EBS-Mount-Dict) |  |
| `spot_fleets `| spot fleet definitions that you'd like to add | no | `list` of [spot fleet dicts](#Spot-Fleet-Dict) ||
| `auto_scaling_groups` | ASG definition that you'd like to add to the custer | no | spot fleet dict object | | |

#### EFS Mount Dict
| var | description | required | type | default |
| - | - | - | - | - |
| `name` | name used for the logical id of the efs mount | Yes |  String | None |
| `efs_id` | the efs id of the Elastic File System you want to mount | Yes | efs-id | None |
| `local_path` | the local path you want to use for the efs mount | Yes | file path, like `/my-efs-directory` | None |

#### EBS Mount Dict
| var | description | required | type | default |
| - | - | - | - | - |
| `name` | logical resource name of the ebs mount | Yes | String | None |
| `device_name` | device mount of the ebs volume | Yes | mount path | None |
| `size` | size of the ebs mount in gigabytes | Yes | Integer | None |

#### Spot Fleet Dict
| var | description | required | type | default |
| - | - | - | - | - |
| `name` | logical resource name of the spot fleet | Yes | String | None |
| `timeout` | spot fleet timeout before instance is terminated | No | minutes in Integer(m) | `2m` |
| `desired_weight` | spot fleet weight of instances, default this to 1 to have all instances be weighted the same | No | Integer | `1` |
| `min_weight` | number of instances or 'weights' that you want as the minimum instances | Yes | Integer | None |
| `max_weight` | number of instances or 'weights' that you want to set as a maximum for the cluster | Yes | Integer | None |
| `task_threshold_out` | If the schedulable tasks dips below this number, scale out | No | Integer | `3` |
| `task_threshold_in` | If the schedulable tasks goes above this number, scale in | No | Integer | `10` |
| `bids` | all the instance types you want to define within your spot fleet | Yes | `list` of [spot fleet bid dicts](#Spot-Fleet-Bid-Dict) | None |

##### Spot Fleet Bid Dict
| var | description | required | type | default |
| - | - | - | - | - |
| `instance_type` | the ec2 instance type you'd like to use | Yes | EC2 Instance Type | None |
| `price` | the max price you want to bid. set this as the reserved price unless you want to live dangerously | Yes | Float | None |
