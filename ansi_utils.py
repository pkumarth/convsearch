import os
import json
import ansible_runner
import subprocess
import sys
import traceback

config = {}
headers = {}


def get_host_res(runner):
    # Initialize a dictionary to hold results for each host
    host_results = {}

    # Process the detailed events for task-level output
    for event in runner.events:
        event_data = event.get('event_data', {})
        host = event_data.get('host')
        if host:
            task = event_data.get('task', 'N/A')
            result = event_data.get('res', {})
            status = event.get('event', 'N/A')
            stdout = event_data.get('stdout', '')

            if host not in host_results:
                host_results[host] = {
                    'tasks': [],
                    'finalout': '',
                    'script_output': [],
                    'return_code': event_data.get('rc', runner.rc),
                }

            if event['event'] == 'runner_on_ok':
                if 'script_output' in event['event_data']['res']:
                    output = event['event_data']['res']['script_output']
                    if output is not None:
                        host_results[host]['script_output'].append(output)

                if 'res' in event['event_data']:
                    rcP = event['event_data'].get('res')
                    if 'rc' in rcP:
                        host_results[host]['return_code'] = rcP.get('rc')
                    finalout = event['event_data']['res']
                    host_results[host]['finalout'] = finalout

            host_results[host]['tasks'].append({
                'task': task,
                'status': status,
                'stdout': stdout,
                'result': result,
            })

    if runner.stats is not None:
        for host, stats in runner.stats.get('hosts', {}).items():
            if host in host_results:
                host_results[host]['stats'] = stats

    transformed_results = []
    for host, details in host_results.items():
        res1 = {
            'hostId': host,
            'hostDetails': details
        }
        transformed_results.append(res1)
    final_result = {
        "stdout": runner.stdout.read(),
        'output': transformed_results
    }
    return final_result


def run_ansible_playbook(playbook, inventory, extra_vars=None):
    print("Running Playbook")
    # Get the private data directory (where ansible-runner will store its data)
    private_data_dir = os.path.join(os.getcwd(), '.ansible-runner')
    os.makedirs(private_data_dir, exist_ok=True)

    runner = ansible_runner.run(
        private_data_dir=private_data_dir,
        playbook=playbook,
        inventory=inventory,
        extravars=extra_vars,
        json_mode=True,
        quiet=True,
        debug=False
    )
    print(f"Runner  res - {runner} {playbook} {inventory} ")
    return get_host_res(runner)


def run_ansible_command(command):
    command.append('-vvv')
    print(f"Running command: {' '.join(command)}")
    result = subprocess.run(command, check=True)
    return result.returncode


def parse_extra_args(extra_args_str):
    extra_vars = {}
    if extra_args_str:
        pairs = extra_args_str.split()
        for pair in pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                extra_vars[key] = value
    return extra_vars


def process_result_default(json_file_path, task_res_file):
    with open(json_file_path, "r") as file:
        data = json.load(file)
    postrun_script_args = data.get("postrun_script_args", [])

    with open(task_res_file, "r") as file:
        result_json = json.load(file)

    return get_result_array(result_json)


def get_result_array(data_task_res):
    hosts = data_task_res["output"]
    scrout = []
    for host in hosts:
        hostname = host["hostId"]
        finalout = host["hostDetails"]["finalout"]
        proc_rc = host["hostDetails"]["return_code"]

        if isinstance(finalout, dict):
            stdout_value = finalout.get("stdout", "")
        else:
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

    return {
        'taskstatus': scrout,
        'data_task_res': hosts
    }


def ansiMain(json_file, output_file, func_name, task_values, app_context):
    global config
    global headers
    config = app_context['config']
    headers = app_context['headers']
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        playbook = data.get('playbook')
        inventory = data.get('inventory')
        extra_vars = data.get('extra_vars', "")

        if not playbook or not inventory:
            raise ValueError("Both 'playbook' and 'inventory' are required fields.")

        ewars = parse_extra_args(extra_vars)
        result = run_ansible_playbook(playbook, inventory, ewars)

        if output_file:
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
        return result

    except Exception as e:
        print(f"An error occurred: {e}")
        print("Stack trace:")
        traceback.print_exc()
        sys.exit(1)

