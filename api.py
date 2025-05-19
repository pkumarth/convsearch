import json
import os
import uuid

import requests

from config import base_url, app_context


def execute_get_request(url, app_context):
    response = requests.get(url, headers=app_context['headers'], verify=False)
    if response.status_code == 200:
        data = response.json()
        print(json.dumps(data, indent=4))
        filepath = os.path.join('/tmp', f"{uuid.uuid4()}.json")
        print(f"response stored at  {filepath}")
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"JSON data successfully stored in {filepath}")
        except Exception as e:
            print(f"Error storing JSON data: {e}")
        return response.json()
    else:
        return None


def execute_post_request(url, payload):
    response = requests.post(url, headers=app_context['headers'], json=payload, verify=False)
    return response


def post_task_event(task_id, task_status, task_logs, progressPercentage):
    url = base_url + "/updateStatus"
    payload = {
        "taskId": f"{task_id}",
        "status": task_status,
        "logMessage": f"{task_logs}",
        "progressPercentage": progressPercentage
    }
    with open("/tmp/pyerr.txt", 'w') as f:
        json.dump(payload, f, indent=2)

    response = execute_post_request(url, payload)
    if response.status_code == 200:
        return response.json()
    else:
        return None


def post_result(task_id, task_result, task_status, task_logs):
    url = base_url + "/completed"
    payload = {
        "taskId": f"{task_id}",
        "result": task_result,
        "status": task_status,
        "logMessage": task_logs
    }
    with open("/tmp/pyerr.txt", 'w') as f:
        json.dump(payload, f, indent=2)

    response = execute_post_request(url, payload)
    if response.status_code == 200:
        return response.json()
    else:
        return None
