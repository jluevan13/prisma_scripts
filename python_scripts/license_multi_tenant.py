import requests
import json
import os


tenants = [
    {
        "tenantName": "tenant4",
        "api": "api4",
        "username": os.environ.get("prismaUserName"),
        "password": os.environ.get("prismaSecretKey"),
    },
    {
        "tenantName": "tenant2",
        "api": "api2",
        "username": os.environ.get("prismaUserName2"),
        "password": os.environ.get("prismaSecretKey2"),
    },
]


def login_prisma(api, username, password):
    ### Create Auth Token for tenant
    url = f"https://{api}.prismacloud.io/login"  # update url based on tenant (i.e, api3, api2, api)
    payload = {}
    payload["username"] = username
    payload["password"] = password
    payload_json = json.dumps(payload)
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json; charset=UTF-8",
    }
    auth_token = requests.request("POST", url, headers=headers, data=payload_json)
    auth_token_data = auth_token.json()
    return auth_token_data["token"]


def get_group_ids(api, token):
    ### Get Group Ids
    url = f"https://{api}.prismacloud.io/cloud/group"  # update url based on tenant (i.e, api3, api2, api)

    group_payload = {}
    group_payload["accountIds"] = []
    headers = {"Accept": "application/json; charset=UTF-8", "x-redlock-auth": token}

    return requests.request("GET", url, headers=headers, data=group_payload).json()


def get_credit_usage(api, group_id, time, unit):
    url = f"https://{api}.prismacloud.io/license/api/v2/usage"  # update url based on tenant (i.e, api3, api2, api)

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


def credit_output(api, group):
    try:
        cost_center = json.loads(group["description"]).get("costCenter")
    except:
        cost_center = "No Cost Center Defined"
    usage_by_group = get_credit_usage(api, group["id"], "1", "month")
    for account in usage_by_group["items"]:
        print(
            f"GroupName:{group['name']}, GroupId:{group['id']}, GroupCostCenter:{cost_center}, AccountName:{account['account']['name']}, AccountId:{account['account']['id']}, AccountCreditUsage:{account['total']}"
        )

    # output = [
    #     f"GroupName:{group['name']}, GroupId:{group['id']}, GroupCostCenter:{cost_center}, AccountName:{account['account']['name']}, AccountId:{account['account']['id']}, AccountCreditUsage:{account['total']}"
    #     for account in usage_by_group["items"]
    # ]

    # print(output)

    # return output


exclude_groups = [
    "JT Account Group",
    "Gorman_IOT_Acct_Group",
    "Gorman Account Group",
]  # list of account groups to exclude from credit allocator

for tenant in tenants:
    token = login_prisma(tenant["api"], tenant["username"], tenant["password"])

    account_groups = get_group_ids(tenant["api"], token)

    group_credits = [
        credit_output(tenant["api"], group)
        for group in account_groups
        if group["name"] not in exclude_groups
    ]

    # print(f"{tenant['tenantName']} -> {group_credits}")
