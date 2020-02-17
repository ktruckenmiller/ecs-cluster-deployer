develop: build-test
	@echo develop
	docker run -it --rm \
	  -v ${PWD}:/code \
	  --workdir=/code \
	  -e AWS_REGION=us-east-2 \
	  -e AWS_DEFAULT_REGION=us-east-2 \
	  -e IAM_ROLE \
		-e VALUES_FILE=tests/regression/infra.yml \
		ktruckenmiller/ecs-cluster-deployer:test sh

generate-dronefile:
	drone jsonnet --stdout --stream > .drone.yml
	drone sign ktruckenmiller/ecs-cluster-deployer --save

build:
	docker build \
	-t ktruckenmiller/ecs-cluster-deployer \
	--build-arg ECS_CLUSTER_DEPLOYER_VERSION=$(shell git rev-parse HEAD) .

build-test:
	docker build \
	-t ktruckenmiller/ecs-cluster-deployer:test \
	--build-arg ECS_CLUSTER_DEPLOYER_VERSION=$(shell git rev-parse HEAD) \
	--target test .

test-ami:
	docker run -it --rm --entrypoint bash \
	-v ${PWD}:${PWD} \
	-w ${PWD} \
	-e IAM_ROLE \
	-e AWS_DEFAULT_REGION=us-east-2 \
	ktruckenmiller/aws-cli

deploy: build
	docker run -it --rm \
	  -v $(shell pwd):/code \
	  --workdir=/code \
	  -e AWS_DEFAULT_REGION=us-west-2 \
		-e VERSION=$(shell git rev-parse HEAD) \
		-e AMI=$(shell cat ami/ecs/ami.txt) \
		-e VALUES_FILE=tests/regression/infra.yml \
	  -e IAM_ROLE \
	  ktruckenmiller/ecs-cluster-deployer deploy

put-pipeline: build
	docker run -it --rm \
		-v ${PWD}:/code \
		--workdir=/code \
		-e AWS_DEFAULT_REGION=us-east-2 \
		-e VERSION=$(shell git rev-parse HEAD) \
		-e IAM_ROLE \
		-e VALUES_FILE=tests/regression/infra.yml \
		ktruckenmiller/ecs-cluster-deployer put-pipeline
