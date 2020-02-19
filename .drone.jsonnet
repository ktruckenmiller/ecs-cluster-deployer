local Bucket(region, env) = {
  name: "upload-linux-"+region,
  image: "plugins/s3",
  depends_on: [ "zip-linux" ],
  settings: {
    access_key: {
      from_secret: "access_key"
    },
    secret_key: {
      from_secret: "secret_key"
    },
    bucket: "kloudcover-public-"+region+"-601394826940",
    acl: "public-read",
    region: region,
    source: "deployment.zip",
    target: if env == "dev" then "ecs_cluster_deployer/${DRONE_COMMIT}" else "ecs_cluster_deployer/${DRONE_TAG}"
  }
};
local Pipeline(env) = {
  kind: "pipeline",
  trigger: {
    event: if env == "dev" then ["push"] else ["tag"]
  },
  name: "deploy-"+env,
  steps: [
    {
      name: "test-deployer",
      image: "python:alpine",
      environment: {
        "AWS_DEFAULT_REGION": "us-west-2"
      },
      commands: [
        "apk add git add gcc musl-dev libffi-dev openssl-dev",
        "pip install -r requirements-dev.pip",
        "pylint ecs_cluster_deployer",
        "pytest --cov-report term --cov=ecs_cluster_deployer tests/ -W ignore::DeprecationWarning"
      ]
    }, {
      name: "coveralls",
      depends_on: [ "test-deployer" ],
      image: "lizheming/drone-coveralls",
      settings: {
        token: {
          from_secret: "coveralls_token"
        },
        files: [".coverage"]
      }
    }, {
      name: "zip-linux",
      depends_on: [ "test-deployer" ],
      image: "alpine",
      commands: [
        "apk add zip unzip",
        "cd ecs_cluster_deployer/lambdas && zip -r deployment.zip *",
        "mv deployment.zip ../../deployment.zip"
      ]
    },
    Bucket("us-east-1", env),
    Bucket("us-west-2", env),
    Bucket("us-east-2", env),
    {
      name: "build-docker",
      image: "plugins/docker",
      depends_on: [ "upload-linux-us-east-1"],
      settings: {
        repo: "ktruckenmiller/ecs-cluster-deployer",
        tags: if env == "dev" then ["latest", "${DRONE_COMMIT}"] else ["${DRONE_TAG}"],
        build_args: [
          if env == "dev" then "ECS_CLUSTER_DEPLOYER_VERSION=${DRONE_COMMIT}" else "ECS_CLUSTER_DEPLOYER_VERSION=${DRONE_TAG}"
        ],
        username: {
          from_secret: "username",
        },
        password: {
          from_secret: "password"
        }
      }
    }
  ]
};


[
  Pipeline("dev"),
  Pipeline("prod")
]
