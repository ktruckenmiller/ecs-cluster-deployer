"""
Index.py entrypoint for ecs cluster deployer

This file should decide the action you'd like to take
"""
import argparse
from ecs_cluster_deployer.entry import put_pipeline, deploy

parser = argparse.ArgumentParser(description='Deploy ecs clusters')
parser.add_argument('action', metavar='action', type=str, nargs='+',
                    help='an action for ecs cluster deployer ie. `deploy` or `put-pipeline`')
args = parser.parse_args()

if 'put-pipeline' in args.action:
    put_pipeline()

if 'deploy' in args.action:
    deploy()
