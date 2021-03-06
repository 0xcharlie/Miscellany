#!/usr/bin/env python2
"""Usage:
  dogmover.py pull (<type>) [--tag=tag]... [--dry-run] [-h]
  dogmover.py push (<type>) [--dry-run] [-h]
  dogmover.py edit (<type>) [--dry-run] [-h]
  dogmover.py validate (<type>) [--dry-run] [-h]

Examples:
    Dashboards:
        dogmover.py pull dashboards
        dogmover.py push dashboards
        dogmover.py edit dashboards
        dogmover.py validate dashboards

    Synthetic api tests using --tag that only pulls tests if the tags exist on them:
        dogmover.py pull synthetic_api_tests --tag env:production --tag application:abc
        dogmover.py push synthetic_api_tests
        dogmover.py edit synthetic_api_tests

    Run with --dry-run without making any changes to your Datadog account:
        dogmover.py pull dashboards --dry-run
        dogmover.py push dashboards --dry-run
        dogmover.py edit dashboards --dry-run
        dogmover.py validate dashboards --dry-run

    Supported arguments:
    dogmover.py pull|push|edit|validate dashboards|monitors|users|synthetics_api_tests|synthetics_browser_tests|awsaccounts|logpipelines|notebooks (--tag=tag) (--dry-run|-h)
    
    Note. --tag is currently only supported for synthetics_api_tests and synthetics_browser_tests.

Options:
  -h, --help
  -d, --dry-run
"""
__author__ = "Misiu Pajor <misiu.pajor@datadoghq.com>"
__version__ = "2.0.5"
from docopt import docopt
import json
import os
import glob
import requests
import logging
import httplib
from datadog import initialize, api

# Debug logging
httplib.HTTPConnection.debuglevel = 1
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
req_log = logging.getLogger('requests.packages.urllib3')
req_log.setLevel(logging.DEBUG)
req_log.propagate = True

def _init_options(action):
    config_file = "config.json"
    try:
        with open(config_file) as f:
            config = json.load(f)
    except IOError:
        exit("No configuration file named: {} could be found.".format(config_file))

    options = {}
    if action == "pull" or action == "edit" or action == "validate":
        options = {
            'api_key': config["source_api_key"],
            'app_key': config["source_app_key"],
            'api_host': config["source_api_host"]
        }
    elif action == "push":
            options = {
                'api_key': config["dest_api_key"],
                'app_key': config["dest_app_key"],
                'api_host': config["dest_api_host"]
            }

    initialize(**options)
    return options

def _ensure_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory

def _json_to_file(path, fileName, data):
    filePathNameWExt = './' + path + '/' + fileName + '.json'
    _ensure_directory(path)
    with open(filePathNameWExt, 'w') as fp:
        json.dump(data, fp, sort_keys = True, indent = 4)
    return filePathNameWExt

def _files_to_json(type):
    files = glob.glob('{}/*.json'.format(type))
    return files

def pull_dashboards():
    path = False
    count = 0

    dashboards = api.Dashboard.get_all()
    for dashboard in dashboards["dashboards"]:
        count = count + 1
        json_data = api.Dashboard.get(dashboard["id"])
        if not arguments["--dry-run"]:
            path = _json_to_file('dashboards', dashboard["id"], json_data)
        print("Pulling dashboard: {} with id: {}, writing to file: {}".format(dashboard["title"].encode('utf8'), dashboard["id"], path))
    print("Retrieved '{}' dashboards.".format(count))

def pull_monitors():
    path = False
    count = 0
    good_keys = ['tags', 'deleted', 'query', 'message', 'matching_downtimes', 'multi', 'name', 'type', 'options', 'id']
    new_monitors = []

    monitors = api.Monitor.get_all()
    for monitor in monitors:
        if monitor["type"] == "synthetics alert":
                print("Skipping {} as this is a monitor belonging to a synthetic test. Synthetic monitors will be automatically re-created when you push synthetic tests.".format(monitor["name"]))
                continue
        count = count + 1
        new_monitor = {}
        for k, v in monitor.items():
            if k in good_keys:
                new_monitor[k] = v
        if not arguments["--dry-run"]:
            path = _json_to_file('monitors', str(new_monitor["id"]), new_monitor)
        print("Pulling monitor: {} with id: {}, writing to file: {}".format(new_monitor["name"].encode('utf8'), new_monitor["id"], path))
    print("Retrieved '{}' monitors.".format(count))

def pull_users():
    path = False
    count = 0

    users = api.User.get_all()
    for user in users["users"]:
        if not user["disabled"]: # don't pull disabled users
            count = count + 1
            json_data = api.User.get(user["handle"])
            if not arguments["--dry-run"]:
                path = _json_to_file('users', user["handle"], json_data["user"])
            print("Pulling user: {} with role: {}, writing to file: {}".format(user["handle"].encode('utf8'), user["access_role"], path))
    print("Retrieved '{}' users.".format(count))


def pull_synthetics_api_tests(options, tag):
    path = False
    count = 0
    tags = [] if not tag else tag

    r = requests.get('{}api/v1/synthetics/tests?api_key={}&application_key={}'.format(options["api_host"], options["api_key"], options["app_key"]))
    synthetics = r.json()
    for synthetic in synthetics["tests"]:
        if synthetic["type"] == "api":
            for tag in tags:
                if tag in synthetic["tags"]:
                    print("Tag: {} found in synthetic test: {}".format(tag, synthetic["name"]))
                    count = count + 1
                    json_data = requests.get('{}api/v1/synthetics/tests/{}?api_key={}&application_key={}'.format(
                        options["api_host"],
                        synthetic["public_id"],
                        options["api_key"],
                        options["app_key"]
                    )).json()
                    path = _json_to_file('synthetics_api_tests', synthetic["public_id"], json_data)
                    print("Pulling: {} and writing to file: {}".format(synthetic["name"].encode('utf8'), path))
    print("Retrieved '{}' synthetic tests.".format(count))

def pull_synthetics_browser_tests(options, tag):
    path = False
    count = 0
    tags = [] if not tag else tag

    r = requests.get('{}api/v1/synthetics/tests?api_key={}&application_key={}'.format(options["api_host"], options["api_key"], options["app_key"]))
    synthetics = r.json()
    for synthetic in synthetics["tests"]:
        if synthetic["type"] == "browser":
            for tag in tags:
                if tag in synthetic["tags"]:
                    print("Tag: {} found in synthetic test: {}".format(tag, synthetic["name"]))
                    count = count + 1
                    json_data = requests.get('{}api/v1/synthetics/tests/browser/{}?api_key={}&application_key={}'.format(
                        options["api_host"],
                        synthetic["public_id"],
                        options["api_key"],
                        options["app_key"]
                    )).json()
                    path = _json_to_file('synthetics_browser_tests', synthetic["public_id"], json_data)
                    print("Pulling: {} and writing to file: {}".format(synthetic["name"].encode('utf8'), path))
    print("Retrieved '{}' synthetic tests.".format(count))


def pull_awsaccounts(options):
    path = False
    count = 0

    r = requests.get('{}api/v1/integration/aws?api_key={}&application_key={}'.format(options["api_host"], options["api_key"], options["app_key"]))
    awsaccounts = r.json()
    for awsaccount in awsaccounts["accounts"]:
        count = count + 1
        if not arguments["--dry-run"]:
            path = _json_to_file('awsaccounts', awsaccount["account_id"], awsaccount)
    print("Retrieved '{}' AWS accounts.".format(count))

def pull_logpipelines(options):
    path = False
    count = 0

    r = requests.get('{}api/v1/logs/config/pipelines?api_key={}&application_key={}'.format(options["api_host"], options["api_key"], options["app_key"]))
    rJSON = r.json()
    for item in rJSON:
        count = count + 1
        path = _json_to_file('logpipelines', item["id"], item)
    print("Retrieved '{}' log pipelines.".format(count))

def pull_notebooks(options):
    path = False
    count = 0

    r = requests.get('{}api/v1/notebook?api_key={}&application_key={}'.format(options["api_host"], options["api_key"], options["app_key"]))
    notebooks = r.json()
    if 'errors' in notebooks: # check if feature flag is enabled in this organisation
        if 'You do not have permission' in notebooks["errors"][0]:
            exit("Notebooks API (notebooks_api) feature flag is not enabled on this Datadog organisation. help@datadoghq.com for more information.")

    for notebook in notebooks["notebooks"]:
        count = count + 1
        path = _json_to_file('notebooks', str(notebook["id"]), notebook)
    print("Retrieved '{}' notebooks.".format(count))     

def push_dashboards():
    count = 0
    dashboards = _files_to_json("dashboards")
    if not dashboards:
        exit("No dashboards are locally available. Consider pulling dashboards first.")

    for dashboard in dashboards:
        with open(dashboard) as f:
            data = json.load(f)
            count = count + 1
            print("Pushing {}".format(data["title"].encode('utf8')))
            if not arguments["--dry-run"]:
                api.Dashboard.create(
                    title=data["title"],
                    description=data["description"],
                    widgets=data["widgets"],
                    template_variables=data["template_variables"],
                    layout_type=data["layout_type"],
                    notify_list=data["notify_list"],
                    is_read_only=data["is_read_only"]
                )
    print("Pushed '{}' dashboards".format(count))


def push_monitors():
    count = 0
    monitors = _files_to_json("monitors")
    if not monitors:
        exit("No monitors are locally available. Consider pulling monitors first.")

    for monitor in monitors:
        with open(monitor) as f:
            data = json.load(f)
            print("Pushing monitors:", data["id"], data["name"].encode('utf8'))
            if not arguments["--dry-run"]:
                result = api.Monitor.create(type=data['type'],
                                    query=data['query'],
                                    name=data['name'],
                                    message=data['message'],
                                    tags=data['tags'],
                                    options=data['options'])
                if 'errors' in result:
                    print('Error pushing monitor:',data["id"],json.dumps(result, indent=4, sort_keys=True))
                    err_count=err_count+1

                else:
                    count = count + 1
                    mon_id= result['id']
                    api.Monitor.mute(mon_id)  
                    
    if count > 0:
        print("Pushed '{}' monitors in muted status, navigate to Monitors -> Manage downtime to unmute.".format(count))
    if err_count > 0:
        print("Error pushing '{}' monitors, please check !".format(err_count))

def edit_monitors():
    err_count = 0
    count = 0
    monitors = _files_to_json("monitors")
    if not monitors:
        exit("No monitors are locally available. Consider pulling monitors first.")

    for monitor in monitors:
        with open(monitor) as f:
            data = json.load(f)
            print("Editing monitors:", data["id"], data["name"].encode('utf8'))
            if not arguments["--dry-run"]:
                result = api.Monitor.update(data["id"], data)

                if 'errors' in result:
                    print('Error Editing monitor:',data["id"],json.dumps(result, indent=4, sort_keys=True))
                    err_count=err_count+1

                else:
                    count = count + 1
                    mon_id= data['id']

    if count > 0:
        print("Edited '{}' monitors ".format(count))
    if err_count > 0:
        print("Error editing '{}' monitors, please check !".format(err_count))

def validate_monitors():
    err_count = 0
    count = 0
    monitors = _files_to_json("monitors")
    if not monitors:
        exit("No monitors are locally available. Consider pulling monitors first.")

    for monitor in monitors:
        with open(monitor) as f:
            data = json.load(f)
            print("Validating monitors:", data["id"], data["name"].encode('utf8'))
            if not arguments["--dry-run"]:
                result = api.Monitor.validate(type=data["type"], query=data["query"], options=data["options"])

                if 'errors' in result:
                    print('Error Validating monitor:',data["id"],json.dumps(result, indent=4, sort_keys=True))
                    err_count=err_count+1

                else:
                    count = count + 1
                    mon_id= data['id']

    if count > 0:
        print("Validateded '{}' monitors ".format(count))
    if err_count > 0:
        print("Error Validating '{}' monitors, please check !".format(err_count))

def push_users():
    count = 0
    users = _files_to_json("users")
    if not users:
        exit("No users are locally available. Consider pulling users first.")

    for user in users:
        with open(user) as f:
            data = json.load(f)
            count = count + 1
            print("Pushing: {}".format(data["handle"].encode('utf8')))
            if not arguments["--dry-run"]:
                api.User.create(
                    handle=data["handle"],
                    name=data["name"],
                    access_role=data["access_role"]
                )
    print("Pushed '{}' users".format(count))

def push_synthetics_api_tests(options):
    count = 0
    synthetics = _files_to_json("synthetics_api_tests")
    if not synthetics:
        exit("No synthetic tests are locally available. Consider synthetics first.")

    for synthetic in synthetics:
         with open(synthetic) as f:
            data = json.load(f)
            count = count + 1
            invalid_keys = ["public_id", "monitor_id"]
            list(map(data.pop, invalid_keys))
            print("Pushing {}".format(data["name"].encode('utf8')))
            if not arguments["--dry-run"]:
                r = requests.post('{}api/v1/synthetics/tests?api_key={}&application_key={}'.format(options["api_host"], options["api_key"], options["app_key"]), json=data)
    print("Pushed '{}' synthetic tests.".format(count))

def push_synthetics_browser_tests(options):
    count = 0
    synthetics = _files_to_json("synthetics_browser_tests")
    if not synthetics:
        exit("No synthetic tests are locally available. Consider synthetics first.")

    for synthetic in synthetics:
         with open(synthetic) as f:
            data = json.load(f)
            count = count + 1
            invalid_keys = ["public_id", "monitor_id"]
            list(map(data.pop, invalid_keys))
            print("Pushing {}".format(data["name"].encode('utf8')))
            if not arguments["--dry-run"]:
                r = requests.post('{}api/v1/synthetics/tests?api_key={}&application_key={}'.format(options["api_host"], options["api_key"], options["app_key"]), json=data)
    print("Pushed '{}' synthetic tests.".format(count))

def push_awsaccounts(options):
    count = 0
    awsaccounts = _files_to_json("awsaccounts")
    if not awsaccounts:
        exit("No awsaccounts are locally available. Consider pulling awsaccounts first.")

    for awsaccount in awsaccounts:
        with open(awsaccount) as f:
            data = json.load(f)
            count = count + 1
            print("Pushing {}".format(data["account_id"].encode('utf8')))
            if not arguments["--dry-run"]:
                r = requests.post('{}api/v1/integration/aws?api_key={}&application_key={}'.format(options["api_host"], options["api_key"], options["app_key"]), json=data)
                json_data = json.loads(r.text)
                json_data["account_id"] = data["account_id"]
                print(json.dumps(json_data))
                path = _json_to_file('awsaccounts.out', data["account_id"], json_data)
    print("Pushed '{}' AWS accounts.".format(count))
    print("You can now use the json files in the awsaccounts.out folder to automate the AWS External ID onboarding using AWS APIs.")

def push_logpipelines(options):
    count = 0
    fJSON = _files_to_json("logpipelines")
    if not fJSON:
        exit("No logpipelines are locally available. Consider pulling logpipelines first.")

    for item in fJSON:
        with open(item) as f:
            data = json.load(f)
            count = count + 1
            print("Pushing {}".format(data["id"].encode('utf8')))
            itemId = data['id']
            del data['id']
            del data['is_read_only']
            del data['type']
            headers = {'content-type': 'application/json'}
            if not arguments["--dry-run"]:
                r = requests.post('{}api/v1/logs/config/pipelines?api_key={}&application_key={}'.format(options["api_host"], options["api_key"], options["app_key"]), headers=headers, json=data)
                json_data = json.loads(r.text)
                json_data["id"] = itemId
                path = _json_to_file('logpipelines.out', itemId, json_data)
    print("Pushed '{}' log pipelines.".format(count))


def push_notebooks(options):
    count = 0
    notebooks = _files_to_json("notebooks")
    if not notebooks:
        exit("No notebooks are locally available. Consider pulling notebooks first.")

    for notebook in notebooks:
        with open(notebook) as f:
            data = json.load(f)
            count = count + 1
            print("Pushing: {}".format(data["name"].encode('utf8')))
            if not arguments["--dry-run"]:
                r = requests.post('{}api/v1/notebook?api_key={}&application_key={}'.format(options["api_host"], options["api_key"], options["app_key"]), json=data)
    print("Pushed '{}' notebooks".format(count))


if __name__ == '__main__':
    arguments = docopt(__doc__, version='0.1.1rc')

    if arguments["--dry-run"]:
        print("You are running in dry-mode. No changes will be commmited to your Datadog account(s).")

    if arguments["pull"]:
        _init_options("pull")
        if arguments['<type>'] == 'dashboards':
            pull_dashboards()
        elif arguments['<type>'] == 'monitors':
            pull_monitors()
        elif arguments['<type>'] == 'users':
            pull_users()
        elif arguments['<type>'] == 'synthetics_api_tests':
            pull_synthetics_api_tests(_init_options("pull"), arguments["--tag"])
        elif arguments['<type>'] == 'synthetics_browser_tests':
            pull_synthetics_browser_tests(_init_options("pull"), arguments["--tag"])
        elif arguments['<type>'] == 'awsaccounts':
            pull_awsaccounts(_init_options("pull"))
        elif arguments['<type>'] == 'logpipelines':
            pull_logpipelines(_init_options("pull"))
        elif arguments['<type>'] == 'notebooks':
            pull_notebooks(_init_options("pull"))               
    elif arguments["push"]:
        _init_options("push")
        if arguments['<type>'] == 'dashboards':
            push_dashboards()
        elif arguments['<type>'] == 'monitors':
            push_monitors()
        elif arguments['<type>'] == 'users':
            push_users()
        elif arguments['<type>'] == 'synthetics_api_tests':
            push_synthetics_api_tests(_init_options("push"))
        elif arguments['<type>'] == 'synthetics_browser_tests':
            push_synthetics_browser_tests(_init_options("push"))
        elif arguments['<type>'] == 'awsaccounts':
            push_awsaccounts(_init_options("push"))
        elif arguments['<type>'] == 'logpipelines':
            push_logpipelines(_init_options("push"))
        elif arguments['<type>'] == 'notebooks':
            push_notebooks(_init_options("push"))
    elif arguments["edit"]:
        _init_options("edit")
        if arguments['<type>'] == 'dashboards':
            edit_dashboards()
        elif arguments['<type>'] == 'monitors':
            edit_monitors()
        elif arguments['<type>'] == 'users':
            edit_users()
        elif arguments['<type>'] == 'synthetics_api_tests':
            edit_synthetics_api_tests(_init_options("edit"))
        elif arguments['<type>'] == 'synthetics_browser_tests':
            edit_synthetics_browser_tests(_init_options("edit"))
        elif arguments['<type>'] == 'awsaccounts':
            edit_awsaccounts(_init_options("edit"))
        elif arguments['<type>'] == 'logpipelines':
            edit_logpipelines(_init_options("edit"))
        elif arguments['<type>'] == 'notebooks':
            edit_notebooks(_init_options("edit"))
    elif arguments["validate"]:
        _init_options("validate")
        if arguments['<type>'] == 'dashboards':
            validate_dashboards()
        elif arguments['<type>'] == 'monitors':
            validate_monitors()
        elif arguments['<type>'] == 'users':
            validate_users()
        elif arguments['<type>'] == 'synthetics_api_tests':
            validate_synthetics_api_tests(_init_options("validate"))
        elif arguments['<type>'] == 'synthetics_browser_tests':
            validate_synthetics_browser_tests(_init_options("validate"))
        elif arguments['<type>'] == 'awsaccounts':
            validate_awsaccounts(_init_options("validate"))
        elif arguments['<type>'] == 'logpipelines':
            validate_logpipelines(_init_options("validate"))
        elif arguments['<type>'] == 'notebooks':
            validate_notebooks(_init_options("validate"))
