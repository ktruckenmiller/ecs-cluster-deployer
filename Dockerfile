FROM python:alpine as base
WORKDIR /ecs_cluster_deployer
RUN apk add git --no-cache
COPY requirements.pip .
RUN pip install -r requirements.pip


FROM base as test
COPY tests/requirements.pip tests/requirements.pip
ENV ECS_CLUSTER_DEPLOYER_VERSION=test
RUN apk add gcc musl-dev && \
    pip install -r tests/requirements.pip
COPY . .

FROM base as dist
ARG ECS_CLUSTER_DEPLOYER_VERSION
ENV ECS_CLUSTER_DEPLOYER_VERSION=$ECS_CLUSTER_DEPLOYER_VERSION
COPY ecs_cluster_deployer /ecs_cluster_deployer
COPY index.py /index.py
ENTRYPOINT ["python", "/index.py"]
