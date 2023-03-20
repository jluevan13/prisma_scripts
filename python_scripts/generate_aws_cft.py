import requests
import json
import os
import boto3
from botocore.exceptions import ClientError
from urllib.parse import unquote


"""
this script is used to automatically update the cloudformation stack for the Prisma Cloud Role.
It can be used to update the role at the organization level, or for individual accounts not in an organization. 

To use the script, you need to define:
export awsAccessKey=<aws access key>
export awsSecretKey=<aws secret key>
export prismaUserName=<prisma cloud access key>
export prismaSecretKey=<prisma cloud secret key>
export awsAccount=<aws account id>
export cfStackId=<cloudformation stack name or arn>
export rootOU=<root ou id>
"""

api = "api4"  # set api based on tenant (api3, api2, api)
prisma_role_name = "PrismaCloudRole"  # update with prisma cloud role name that is defined in prisma console

### Set up aws credentials
session = boto3.session.Session(
    aws_access_key_id=os.environ.get("awsAccessKey"),
    aws_secret_access_key=os.environ.get("awsSecretKey"),
    region_name="us-east-1",
    profile_name="security",
)

cf_client = session.client("cloudformation")


### Create Auth Token for tenant
login_url = f"https://{api}.prismacloud.io/login"

login_payload = {}
login_payload["username"] = os.environ.get("prismaUserName")
login_payload["password"] = os.environ.get("prismaSecretKey")
payload_json = json.dumps(login_payload)
headers = {
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "application/json; charset=UTF-8",
}

auth_token = requests.request("POST", login_url, headers=headers, data=payload_json)
token = auth_token.json()["token"]

### Get supported features
### Supported features for aws organizations are listed below
features_url = f"https://{api}.prismacloud.io/cas/v1/features/cloud/aws"

supported_features_payload = json.dumps(
    {
        "accountType": "organization",  # change this to account for an individual account not in an organization
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
    "POST", features_url, headers=headers, data=supported_features_payload
)

# print(supported_features.json())
# Supported Features -> 'supportedFeatures': ['Agentless Scanning', 'Auto Protect', 'Cloud Visibility Compliance and Governance', 'Remediation', 'Serverless Function Scanning']


# Generate s3 presigned url with template
template_url = f"https://{api}.prismacloud.io/cas/v1/aws_template/presigned_url"

template_payload = json.dumps(
    {
        "accountType": "organization",  # change this to account for an individual account not in an organization
        "accountId": os.environ.get("awsAccount"),
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
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "x-redlock-auth": token,
}

template_response = requests.request(
    "POST", template_url, headers=headers, data=template_payload
)


### Update the stack with the new template
try:
    response = cf_client.update_stack(
        StackName=os.environ.get("cfStackId"),
        TemplateURL=unquote(
            template_response.json()["createStackLinkWithS3PresignedUrl"].split(
                "templateURL="
            )[1]
        ),
        Parameters=[
            {
                "ParameterKey": "OrganizationalUnitIds",
                "ParameterValue": os.environ.get("rootOU"),
            },
            {"ParameterKey": "PrismaCloudRoleName", "ParameterValue": prisma_role_name},
        ],
        Capabilities=["CAPABILITY_NAMED_IAM"],
    )
except ClientError as e:
    print(str(e))
