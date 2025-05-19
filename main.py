import json
import os
from datetime import datetime
import uuid
import base64
from api import execute_get_request, post_task_event, post_result
from config import load_config, app_context, base_url, task_portal_client_id, task_portal_client_secret, \
    adsk_portal_client_id, adsk_portal_client_secret, sentinel_token, tasks_dir, sentinel_api_key, playbooks_dir
from pyscript.edr_utils import get_win_edr_config, get_linux_edr_config
from ansi_utils import ansiMain


def get_playbook_path(taskType, taskSubType):
    playbook_path = ""
    playbook_path = {
        "MAC_PATCH": app_context.config.get("playbooks").get("mac_updates"),
        "LINUX_PATCH": app_context.config.get("playbooks").get("linux_updates"),
        "WINDOWS_PATCH": app_context.config.get("playbooks").get("windows_updates"),
        "INSTALL_LINUX_EDR": app_context.config.get("playbooks").get("linux_edr_install"),
        "INSTALL_MAC_EDR": app_context.config.get("playbooks").get("mac_edr_install"),
        "WIN_EDR_INSTALL": app_context.config.get("playbooks").get("win_edr_install")
    }.get(taskSubType.upper(), "")
    return playbook_path


def default_handler(*args):
    # Default handler that takes any number of arguments and returns empty dict
    return {}


def install_linux_edr(*args):
    # Implement Linux EDR specific logic here
    # Return dictionary with required key-value pairs
    print(f"LNX {args}")
    account_id = args[0]
    return get_linux_edr_config(adsk_portal_client_id, adsk_portal_client_secret, sentinel_token, sentinel_api_key,
                                account_id)


def install_win_edr(*args):
    try:
        return get_win_edr_config(args[0])
    except ImportError:
        # Fallback values if import fails
        return {
        }


def prepare_json(taskType, taskSubType, template_data_str, inventory_path, task_type, task_id, extra_args):
    # def prepare_json(template_data, inventory_path, task_type, output_filename, argdata):
    # Read template JSON file

    # Get task specific values based on task_type
    print(f"\n\n{template_data_str}")
    template_data = {}  # json.loads(template_data_str)
    task_handlers = {
        "install_win_edr": install_win_edr,
        "install_linux_edr": install_linux_edr
    }

    # Use default_handler instead of lambda
    task_values = {}
    if task_type:
        handler = task_handlers.get(task_type, default_handler)
        task_values = handler(extra_args)

    # Update extra_vars if task_values is not empty
    if task_values:
        extra_vars = " ".join([f"{k}={v}" for k, v in task_values.items()])
        extra_vars = f"target_hosts=all {extra_vars}"
        template_data["extra_vars"] = extra_vars

    # Update inventory path
    template_data["inventory"] = inventory_path
    template_data["playbook"] = app_context.config.get("playbooks_dir") + get_playbook_path(taskType, taskSubType)

    print(f"TASK JSON {template_data}")
    return template_data


def write_to_file(data, file_path):
    try:
        with open(file_path, 'w') as file:
            if isinstance(data, list):
                file.writelines(line + '\n' for line in data)
            else:
                file.write(str(data))
        print(f"Data written successfully to {file_path}")

    except Exception as e:
        print(f"Error writing to file: {e}")


def get_result_array(data_task_res):
    hosts = data_task_res["output"]
    scrout = []
    for host in hosts:
        hostname = host["hostId"]
        finalout = host["hostDetails"]["finalout"]

        proc_rc = host["hostDetails"]["return_code"]  # finalout.get("return_code", "")

        if isinstance(finalout, dict):
            stdout_value = finalout.get("stdout", "")
        else:
            # Handle the case where finalout is a string
            stdout_value = finalout

        output_code = 1200
        output_status = "Successfuly Done!"

        if proc_rc != 0:
            output_code = 1501
            output_status = "Task Failed"

        hout = {
            'hostname': hostname,
            'code': output_code,
            'stdout': stdout_value,
            'status': output_status
        }
        scrout.append(hout)

    final_out = {
        'taskstatus': scrout,
        'data_task_res': hosts
    }
    return final_out


def process_result_default(json_file_path, task_res_file):
    # Read the JSON file
    with open(json_file_path, "r") as file:
        data = json.load(file)
    # Access the 'postrun_script_args' list
    postrun_script_args = data.get("postrun_script_args", [])

    # Read the JSON file
    with open(task_res_file, "r") as file:
        result_json = json.load(file)

    json_obj = get_result_array(result_json)
    return json_obj


def run_ansible(task_file_name, result_file_name, trigger, eargs):
    result = ansiMain(task_file_name, result_file_name, trigger, eargs, app_context)
    dockerlogs = result
    final_res = process_result_default(task_file_name, result_file_name)
    print(f"{final_res}")

    resdict = {}
    resdict["dockerlogs"] = dockerlogs
    resdict["final_res"] = final_res

    # Process the output
    return resdict


def execute_tasks():
    # Create directories if they do not exist
    if not os.path.exists(tasks_dir):
        os.makedirs(tasks_dir)
    # Generate dynamic filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())

    task_file_name = f"task_{unique_id}_{timestamp}.json"
    task_file_path = f"{tasks_dir}{task_file_name}"

    inventory_name = f"inventory_{timestamp}_{unique_id}.ini"
    inventory_file = f"{tasks_dir}{inventory_name}"
    inventory_file_key = inventory_file

    result_file_name = f"task_result_{unique_id}_{timestamp}.json"
    result_file_path = f"{tasks_dir}{result_file_name}"
    logfilename = f"task_logs_{unique_id}_{timestamp}.log"

    # url =  "https://kimaya.appdb.io//staticfs/test-task.json"
    url = base_url + "/getTasks"
    response = execute_get_request(url, app_context)
    if response:
        if response.get("success"):
            tasks = response.get("result", {}).get("tasks", [])
            for taskNodes in tasks:
                for taskNode in taskNodes:
                    try:
                        # print(taskNode['taskInput'])
                        taskRaw = base64.b64decode(taskNode['taskInput'])
                        print("\n\n\n\n")
                        print(taskRaw)
                        task = json.loads(taskRaw)
                        taskId = taskNode['taskId']
                        taskName = taskNode['taskName']
                        taskType = taskNode['taskType']
                        taskSubType = taskNode['taskSubType']
                        taskStatus = taskNode['taskStatus']
                        task['taskId'] = taskId

                        task['template'] = base64.b64decode(task['template']).decode('utf-8')
                        task['inventory'] = base64.b64decode(task['inventory']).decode('utf-8')
                        task['eargs'] = ""
                        # remove hard coded eargs

                        # task['trigger'] = taskNode['taskInput']['trigger']
                        # task['taskid'] = taskNode['taskInput']['taskid']
                        # task['eargs'] = taskNode['taskInput']['eargs']

                        write_to_file(task['inventory'], inventory_file)
                        print(f"Created Inv. File {inventory_file} \n\n")

                        print(f"Template {task['template']}\n\n")

                        task_data = prepare_json(taskType, taskSubType, task['template'], inventory_file_key,
                                                 task['trigger'], task['taskId'], task['eargs'])

                        with open(task_file_path, 'w') as f:
                            json.dump(task_data, f, indent=2)

                        print(f"Created Task File {task_file_path}")

                        # post_task_event(taskId,"IN_PROGRESS",task_data,20)

                        print("Deploying Docker")
                        resdict = run_ansible(task_file_path, result_file_path, task['trigger'], task['eargs'])
                        print("Docker Job Finished")
                        post_task_event(taskId, "IN_PROGRESS", resdict["dockerlogs"], 75)

                        print("Posting Result")
                        dockerlogs = resdict["dockerlogs"]
                        final_res = resdict["final_res"]
                        post_result(task['taskId'], final_res, 'COMPLETED', dockerlogs)

                        print(
                            f"Template: {task['template']}, Inventory: {task['inventory']}, Trigger: {task['trigger']}")
                    except Exception as e:
                        print(f"Error processing task: {e}")
                        post_result(task['taskid'], {e}, 'FAILED', {e})

        else:
            print("Failed to retrieve tasks. Check the API response for more details.")
    else:
        print("Failed to connect to the API. Check the API endpoint and credentials.")


if __name__ == "__main__":
    # if len(sys.argv) < 2:
    #     print("Error: Configuration file path not provided")
    #     print("Usage: python kimaya-ansi-agent.py <path_to_config_file>")
    #     sys.exit(1)

    config_path = "agent.conf"  # sys.argv[1]
    # Load configuration
    app_context = load_config(config_path)
    execute_tasks()
