REGION ?= {{cookiecutter.Region}}

put-pipeline:
	docker run -it --rm \
		-v ${PWD}:${PWD} \
		-w ${PWD} \
		-v ~/.aws/credentials:/root/.aws/credentials:ro \
		-e AWS_DEFAULT_REGION=$(REGION) \
		ktruckenmiller/ecs-cluster-deployer put-pipeline

.PHONY: put-pipeline
