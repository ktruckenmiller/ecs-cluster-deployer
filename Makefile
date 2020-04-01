REGION ?= "us-east-2"
ECS_CLUSTER_DEPLOYER_VERSION := $(shell git rev-parse HEAD)

develop: build-test
	@echo develop
	docker run -it --rm \
	  -v ${PWD}:/code \
	  --workdir=/code \
	  -e AWS_DEFAULT_REGION=$(REGION) \
	  -e IAM_ROLE \
		-e VALUES_FILE=tests/regression/infra.yml \
		ktruckenmiller/ecs-cluster-deployer:test sh

sign:
	drone jsonnet --stdout --stream > .drone.yml
	drone sign ktruckenmiller/ecs-cluster-deployer --save
	git add .drone.yml .drone.jsonnet
	git commit -m 'signed dronefile'
	git push

build:
	docker build \
	-t ktruckenmiller/ecs-cluster-deployer \
	--build-arg ECS_CLUSTER_DEPLOYER_VERSION=$ECS_CLUSTER_DEPLOYER_VERSION .

build-test:
	docker build \
	-t ktruckenmiller/ecs-cluster-deployer:test \
	--build-arg ECS_CLUSTER_DEPLOYER_VERSION=$ECS_CLUSTER_DEPLOYER_VERSION \
	--target test .

unit: build-test
	docker run -it --rm \
		-e AWS_DEFAULT_REGION=$(REGION) \
		ktruckenmiller/ecs-cluster-deployer:test \
		pytest tests/unit \
		-n 2 \
		--cov-report term \
		--cov=ecs_cluster_deployer tests \
		-W ignore::DeprecationWarning

test-template: build
	docker run -it --rm \
		-w ${PWD} \
		-v ${PWD}/fake-dir:${PWD} \
		-e AWS_DEFAULT_REGION=$(REGION) \
		-e VERSION=$ECS_CLUSTER_DEPLOYER_VERSION \
		-e IAM_ROLE \
		ktruckenmiller/ecs-cluster-deployer template

test-ami:
	docker run -it --rm --entrypoint bash \
	-v ${PWD}:${PWD} \
	-w ${PWD} \
	-e IAM_ROLE \
	-e AWS_DEFAULT_REGION=$(REGION) \
	ktruckenmiller/aws-cli

deploy: build
	docker run -it --rm \
	  -v ${PWD}:/code \
	  --workdir=/code \
	  -e AWS_DEFAULT_REGION=$(REGION) \
		-e VERSION=$ECS_CLUSTER_DEPLOYER_VERSION \
		-e AMI=$(shell cat ami/ecs/ami.txt) \
		-e VALUES_FILE=tests/regression/infra.yml \
	  -e IAM_ROLE \
	  ktruckenmiller/ecs-cluster-deployer deploy

put-pipeline: build
	docker run -it --rm \
		-v ${PWD}:/code \
		--workdir=/code \
		-e AWS_DEFAULT_REGION=$(REGION) \
		-e VERSION=$ECS_CLUSTER_DEPLOYER_VERSION \
		-e IAM_ROLE \
		-e VALUES_FILE=tests/regression/infra.yml \
		ktruckenmiller/ecs-cluster-deployer put-pipeline
