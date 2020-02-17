""" Custom utils for the ECS Deployer """
import os
import logging
import zipfile
import boto3
from botocore.client import ClientError

logger = logging.getLogger()
logging.basicConfig()
logger.setLevel(logging.INFO)

def sanitize_cfn_resource_name(name):
    """ Sets Logical Name in CloudFormation """
    name = ''.join([n.title() for n in name.split('-')])
    return name


class PushArtifacts:
    """ pushes artifacts to s3 """
    def __init__(self, ecs_obj):
        self.cluster_name = ecs_obj.base['cluster']['name']
        self.bucket = ecs_obj.s3_bucket
        self.version = ecs_obj.version
        self.region = ecs_obj.region
        self.s3 = boto3.resource('s3', region_name=self.region)
        self.upload_artifacts()

    @staticmethod
    def zip(src, dst):
        """ Zip files """
        zf = zipfile.ZipFile("{}.zip".format(dst), "w", zipfile.ZIP_DEFLATED)
        abs_src = os.path.abspath(src)
        for dirname, _, files in os.walk(src):

            for filename in files:
                if '.pyc' not in filename:
                    absname = os.path.abspath(os.path.join(dirname, filename))
                    arcname = absname[len(abs_src) + 1:]
                    print('zipping {} as {}'.format(os.path.join(dirname, filename), arcname))
                    zf.write(absname, arcname)
        zf.close()



    def zip_files(self):
        """ Zip these files """
        self.zip("ecs_cluster_deployer/lambdas", "deployment")

    def upload_artifacts(self):
        """ Uploads artifacts, creates bucket if we need it """
        logger.info('Uploading artifacts...')
        logger.info(self.region)
        logger.info(self.bucket)

        self.zip_files()
        try:
            self.s3.meta.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            logger.warning(e)
            # The bucket does not exist or you have no access.
            if self.region == 'us-east-1':
                self.s3.create_bucket( #pylint: disable=E1101
                    Bucket=self.bucket
                )
            else:
                self.s3.create_bucket( #pylint: disable=E1101
                    Bucket=self.bucket,
                    CreateBucketConfiguration={
                        "LocationConstraint": self.region
                    }
                )

        prefix = "{}/{}".format(self.cluster_name, self.version)
        self.s3.meta.client.upload_file("deployment.zip", self.bucket, "{}/{}".format(prefix, "deployment.zip"))
