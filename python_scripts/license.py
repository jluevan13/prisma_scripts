import requests
import json
import os


### Create Auth Token for tenant
url = (
    "https://api4.prismacloud.io/login"  # update url based on tenant (i.e, app3, app2)
)

payload = {}
payload["username"] = os.environ.get("prismaUserName")
payload["password"] = os.environ.get("prismaSecretKey")
payload_json = json.dumps(payload)
headers = {
    "Content-Type": "application/json; charset=UTF-8",
    "Accept": "application/json; charset=UTF-8",
}

auth_token = requests.request("POST", url, headers=headers, data=payload_json)
auth_token_data = auth_token.json()
token = auth_token_data["token"]

### Get Group Ids
url = "https://api4.prismacloud.io/cloud/group"

group_payload = {}
group_payload["accountIds"] = []
headers = {"Accept": "application/json; charset=UTF-8", "x-redlock-auth": token}

account_groups = requests.request("GET", url, headers=headers, data=payload)


def get_credit_usage(group_id, time, unit):
    url = "https://api4.prismacloud.io/license/api/v2/usage"

    usage_payload = {}
    usage_payload["accountIds"] = []
    usage_payload["accountGroupIds"] = [group_id]
    usage_payload["cloudTypes"] = [
        "aws",
        "azure",
        "oci",
        "alibaba_cloud",
        "gcp",
        "others",
        "repositories",
    ]
    usage_payload["timeRange"] = {
        "type": "relative",
        "value": {"amount": time, "unit": unit},
    }
    usage_payload_json = json.dumps(usage_payload)

    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json; charset=UTF-8",
        "x-redlock-auth": token,
    }
    response = requests.request("POST", url, headers=headers, data=usage_payload_json)

    return response.json()


for group in account_groups.json():
    usage_by_group = get_credit_usage(group["id"], "1", "month")
    print(f'{group["id"]}: {usage_by_group["stats"]["total"]}')
