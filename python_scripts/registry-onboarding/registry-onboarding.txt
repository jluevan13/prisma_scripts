import requests
import json
import os

### Path to the Prisma Cloud Compute Console
### Found at Runtime Security > Manage > System > Utilities > Path to Console
### Should not include 'https://'
### Example app0.cloud.twistlock.com/app0-xxxxxxxxx
console_path = os.environ.get("CONSOLE_PATH")

### Authenticate to Prisma Cloud Compute
### Response is an authentication token, which is passed in the response for the subsequent steps

url = f"https://{console_path}/api/v32.06/authenticate"

auth_payload = json.dumps(
    {
        "password": os.environ.get("PC_PASS"),
        "username": os.environ.get("PC_USER"),
    }
)
headers = {"Content-Type": "application/json", "Accept": "application/json"}
auth_token = requests.request("POST", url, headers=headers, data=auth_payload).json()[
    "token"
]
# print(auth_token)


### Get Cloud Radar Undefended Registries
### Currently the payload is not passed in the response so the url has been updated to check for undefended azure registries

url = f"https://{console_path}/api/v32.06/cloud/discovery/entities?serviceType=azure-acr&defended=false"

payload = {
    "provided": ["azure"],
    "serviceType": ["azure-acr"],
}  #### Payload isn't added to the request
headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": f"Bearer {auth_token}",
}

undefeded_resources = requests.request(
    "GET", url, headers=headers, data=json.dumps(payload)
).json()

# print(undefeded_resources)

### Add undefended registries
### If there are no azure registries returned above, don't attempt to add new entries
### For each azure registry returned above, create a new entry with the registry and repositor name using the credentials (service principal created)
url = f"https://{console_path}/api/v32.06/settings/registry"

if undefeded_resources == None:
    print("No undefended azure registries.")
else:
    for registry in undefeded_resources:
        payload = json.dumps(
            {
                "version": registry["provider"],
                "registry": registry["registry"],
                "repository": registry["name"],
                "credentialID": "jt-security-sub",  ### currently hardcoded
                "os": "linux",
                "harborDeploymentSecurity": False,
                "collections": ["All"],
                "cap": 5,
                "scanners": 2,
                "versionPattern": "",
            },
        )
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {auth_token}",
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        print(response)
