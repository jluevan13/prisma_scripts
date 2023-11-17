import requests
import json
import boto3
import base64
import os
import logging
from botocore.exceptions import ClientError
from urllib.parse import unquote

logging.getLogger().setLevel(logging.INFO)

api = "api4"  # set api based on tenant (api3, api2, api)
prisma_role_name = "PrismaCloudRole"  # update with prisma cloud role name that is defined in prisma console
secret_name = "prod/prismaSecret"
user_name = "prod/prismaUser"

### Set up aws credentials
session = boto3.session.Session()

cf_client = session.client("cloudformation")

secret_client = session.client("secretsmanager")


def handler(event, context):
    ### Get Prisma Secret Key
    try:
        secret_value_response = secret_client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        logging.debug(f"error getting prisma secret key: {e}")
    else:
        prismaSecretKey = json.loads(secret_value_response["SecretString"])[
            "prismaSecret"
        ]

    ### Get Prisma user name
    try:
        secret_value_response = secret_client.get_secret_value(SecretId=user_name)
    except ClientError as e:
        logging.debug(f"error getting prisma user name: {e}")
    else:
        prismaUserName = json.loads(secret_value_response["SecretString"])[
            "prismaUserName"
        ]

    ### Create Auth Token for tenant
    try:
        login_url = f"https://{api}.prismacloud.io/login"

        login_payload = {}
        login_payload["username"] = prismaUserName
        login_payload["password"] = prismaSecretKey
        payload_json = json.dumps(login_payload)
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json; charset=UTF-8",
        }
    except:
        logging.debug("error logging into prisma cloud")
    else:
        auth_token = requests.request(
            "POST", login_url, headers=headers, data=payload_json
        )
        token = auth_token.json()["token"]
        logging.info("successful login to prisma cloud")

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
            "accountId": os.environ.get("AWSACCOUNT"),
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

    logging.info(f"template url response: {template_response.json()}")

    ### Update the stack with the new template
    try:
        logging.info(f"starting to update stack {os.environ.get('STACK_ID')}")
        response = cf_client.update_stack(
            StackName=os.environ.get("STACK_ID"),
            TemplateURL=unquote(
                template_response.json()["createStackLinkWithS3PresignedUrl"].split(
                    "templateURL="
                )[1]
            ),
            Parameters=[
                {
                    "ParameterKey": "OrganizationalUnitIds",
                    "ParameterValue": os.environ.get("ROOTOU"),
                },
                {
                    "ParameterKey": "PrismaCloudRoleName",
                    "ParameterValue": prisma_role_name,
                },
            ],
            Capabilities=["CAPABILITY_NAMED_IAM"],
        )

        logging.info(f"finished updating stack: {response}")
    except ClientError as e:
        logging.debug(f"error updating stack: {e}")
