import requests
import json
import os
from pandas import DataFrame as df


def credit_allocator():
    tenants = [
        {
            "tenantName": "tenant4",
            "api": "api4",
            "username": os.environ.get("prismaUserName"),
            "password": os.environ.get("prismaSecretKey"),
        },
        # {
        #     "tenantName": "tenant2",
        #     "api": "api",
        #     "username": os.environ.get("prismaUserName2"),
        #     "password": os.environ.get("prismaSecretKey2"),
        # },
        # {
        #     "tenantName": "tenant3",
        #     "api": "api2",
        #     "username": os.environ.get("prismaUserName3"),
        #     "password": os.environ.get("prismaSecretKey3"),
        # },
        # {
        #     "tenantName": "tenant4",
        #     "api": "api2-eu",
        #     "username": os.environ.get("prismaUserName4"),
        #     "password": os.environ.get("prismaSecretKey4"),
        # },
    ]

    licensing_role = "Licensing Role"  # role name of licensing role
    licensing_group = (
        "Licensing Group"  # group name of Permission Group assigned to licensing role
    )

    allocated_accounts = []
    for tenant in tenants:
        token = login_prisma(tenant["api"], tenant["username"], tenant["password"])
        usage_by_account = get_credit_usage(
            tenant["tenantName"], tenant["api"], token, "1", "month"
        )
        account_info = list_accounts(tenant["api"], token)

        groups = get_group_ids(tenant["api"], token)

        role_id = get_role_id(tenant["api"], token, licensing_role, licensing_group)

        update_user_role(
            tenant["api"], token, licensing_role, licensing_group, groups, role_id
        )

        mapped_accounts = map_accounts_groups(usage_by_account, account_info, groups)

        allocated_accounts.extend(mapped_accounts)

    dataFrame = df.from_dict(allocated_accounts)
    dataFrame.to_csv("credit_allocator.csv")


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


def get_credit_usage(tenantName, api, token, time, unit):
    url = f"https://{api}.prismacloud.io/license/api/v2/usage"  # update url based on tenant (i.e, api3, api2, api)

    usage_payload = {}
    usage_payload["accountIds"] = []
    # usage_payload["accountGroupIds"] = [group_id]
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
    usage_by_account = requests.request(
        "POST", url, headers=headers, data=usage_payload_json
    ).json()
    exclude_account_name = ["others"]
    license_info = []
    for account in usage_by_account["items"]:
        if account["account"]["name"] not in exclude_account_name:
            license_dict = {}
            license_dict["accountName"] = account["account"]["name"]
            license_dict["accountId"] = account["account"]["id"]
            license_dict["cloudType"] = account["cloudType"]
            license_dict["totalCredits"] = account["total"]
            license_dict["tenantName"] = tenantName
            license_info.append(license_dict)
    return license_info


def list_accounts(api, token):
    url = f"https://{api}.prismacloud.io/cloud"

    payload = {}
    headers = {
        "Accept": "application/json; charset=UTF-8",
        "x-redlock-auth": token,
    }

    account_list = requests.request("GET", url, headers=headers, data=payload).json()

    orgs = [account for account in account_list if account["accountType"] != "account"]
    for org in orgs:
        cloud_type = org["cloudType"]
        account_id = org["accountId"]

        org_url = (
            f"https://{api}.prismacloud.io/cloud/{cloud_type}/{account_id}/project"
        )

        org_response = requests.request(
            "GET", org_url, headers=headers, data=payload
        ).json()
        for member in org_response:
            if member["accountType"] == "account":
                account_list.append(member)
    return account_list


def get_group_ids(api, token):
    ### Get Group Ids
    url = f"https://{api}.prismacloud.io/cloud/group"  # update url based on tenant (i.e, api3, api2, api)

    group_payload = {}
    headers = {"Accept": "application/json; charset=UTF-8", "x-redlock-auth": token}

    return requests.request("GET", url, headers=headers, data=group_payload).json()


def get_role_id(api, token, licensing_role, licensing_group):
    url = f"https://{api}.prismacloud.io/user/role"
    get_role_payload = {}

    headers = {
        "Accept": "application/json; charset=UTF-8",
        "x-redlock-auth": token,
    }

    roles_list = requests.request(
        "GET", url, headers=headers, data=get_role_payload
    ).json()

    role_id = [role["id"] for role in roles_list if role["name"] == licensing_role]
    return role_id[0]


def update_user_role(
    api, token, licensing_role, licensing_group, account_groups, role_id
):
    account_group_ids = [group["id"] for group in account_groups]

    url = f"https://{api}.prismacloud.io/user/role/{role_id}"

    role_payload = {
        "name": licensing_role,  # Update this to your role name
        "description": "Updated Licensing Role with all account groups",  # Update description as needed
        "accountGroupIds": account_group_ids,
        "roleType": licensing_group,
    }

    role_payload_json = json.dumps(role_payload)

    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json; charset=UTF-8",
        "x-redlock-auth": token,
    }
    response = requests.request("PUT", url, headers=headers, data=role_payload_json)
    return response


def map_accounts_groups(usage_by_account, account_info, groups_meta):
    for item in usage_by_account:
        for account in account_info:
            if account["accountId"] == item["accountId"]:
                group_num = 1
                sorted_groups = sorted(
                    account["groups"],
                    key=lambda d: "All" in d["name"],
                    reverse=False,
                )
                for group in sorted_groups:
                    group_descrption = [
                        group_info["description"]
                        for group_info in groups_meta
                        if group_info["id"] == group["id"]
                    ][0]
                    item[f"groupId{group_num}"] = group["id"]
                    item[f"groupName{group_num}"] = group["name"]
                    item[f"groupDescription{group_num}"] = group_descrption
                    group_num += 1
    return usage_by_account


credit_allocator()
