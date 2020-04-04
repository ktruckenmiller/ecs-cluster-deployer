FROM python:alpine as base
WORKDIR /ecs_cluster_deployer
RUN apk add git curl --no-cache
COPY requirements.pip .
RUN pip install -r requirements.pip


FROM base as test
COPY requirements-dev.pip requirements-dev.pip
COPY requirements.pip requirements.pip
ENV ECS_CLUSTER_DEPLOYER_VERSION=test
RUN apk --no-cache add \
        gcc \
        musl-dev \
        libffi-dev \
        openssl-dev && \
    pip install -r requirements-dev.pip

COPY . .

FROM base as dist
ARG ECS_CLUSTER_DEPLOYER_VERSION
ENV ECS_CLUSTER_DEPLOYER_VERSION=$ECS_CLUSTER_DEPLOYER_VERSION
COPY cookiecutter /cookiecutter
COPY ecs_cluster_deployer /ecs_cluster_deployer
COPY index.py /index.py
ENTRYPOINT ["python", "/index.py"]
