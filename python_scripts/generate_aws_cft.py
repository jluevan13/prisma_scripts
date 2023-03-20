import requests
import json
import os
import boto3
from botocore.exceptions import ClientError

api = "api4"  # set api based on tenant (api3, api2, api)

### Create Auth Token for tenant
login_url = f"https://{api}.prismacloud.io/login"

payload = {}
payload["username"] = os.environ.get("prismaUserName")
payload["password"] = os.environ.get("prismaSecretKey")
payload_json = json.dumps(payload)
headers = {
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "application/json; charset=UTF-8",
}

auth_token = requests.request("POST", login_url, headers=headers, data=payload_json)
auth_token_data = auth_token.json()
token = auth_token_data["token"]


### Get supported features
url = f"https://{api}.prismacloud.io/cas/v1/features/cloud/aws"

supported_features_payload = json.dumps(
    {
        "accountType": "organization",
        "awsPartition": "us-east-1",
        "rootSyncEnabled": True,
    }
)
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "x-redlock-auth": token,
}

supported_features = requests.request(
    "POST", url, headers=headers, data=supported_features_payload
)

# print(supported_features.json())
# Supported Features -> 'supportedFeatures': ['Agentless Scanning', 'Auto Protect', 'Cloud Visibility Compliance and Governance', 'Remediation', 'Serverless Function Scanning']


## Generate CFT
url = f"https://{api}.prismacloud.io/cas/v1/aws_template"
account_id = os.environ.get("awsAccount")
generate_cft_payload = json.dumps(
    {
        "accountType": "organization",
        "accountId": account_id,
        "awsPartition": "us-east-1",
        "features": [
            "Agentless Scanning",
            "Auto Protect",
            "Cloud Visibility Compliance and Governance",
            "Remediation",
            "Serverless Function Scanning",
        ],
    }
)
headers = {"Content-Type": "application/json", "x-redlock-auth": token}

cft = requests.request("POST", url, headers=headers, data=generate_cft_payload)

with open("prisma_org_role.template", "w") as f:
    f.write(cft.text)

session = boto3.session.Session(
    aws_access_key_id=os.environ.get("awsAccessKey"),
    aws_secret_access_key=os.environ.get("awsSecretKey"),
    region_name="us-east-1",
    profile_name="security",
)

cf_client = session.client("cloudformation")
s3_client = session.resource("s3")

bucket_name = os.environ.get("prismaBucketName")
object_key = "prisma_org_role.template"

s3_client.meta.client.upload_file(
    "prisma_org_role.template",  # path to file
    bucket_name,
    object_key,
)

root_ou = os.environ.get("rootOU")
cf_stack_arn = os.environ.get("cfStackId")
prisma_role_name = "PrismaCloudRole"  # update with prisma cloud role name that is defined in prisma console

try:
    response = cf_client.update_stack(
        StackName=cf_stack_arn,
        TemplateURL=f"https://{bucket_name}.s3.amazonaws.com/{object_key}",
        Parameters=[
            {"ParameterKey": "OrganizationalUnitIds", "ParameterValue": root_ou},
            {"ParameterKey": "PrismaCloudRoleName", "ParameterValue": prisma_role_name},
        ],
        Capabilities=["CAPABILITY_NAMED_IAM"],
    )
except ClientError as e:
    print(str(e))
