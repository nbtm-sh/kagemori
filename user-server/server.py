import flask
import os
import socket
import yaml 
import subprocess
import getpass
import json
import time
import threading
import datetime
import psutil
from flask import request, jsonify
from auth.pam_backend import AuthBackend
from session.session_manager import Session, SessionManager

app = flask.Flask(__name__)
au = AuthBackend()
sm = SessionManager()

# Load server configuraiton
config = {}
with open("./config.yaml", "r") as config_fp:
    config = yaml.safe_load(config_fp)

def format_path(path):
    path = os.path.expanduser(path) 

    return path

SOCK=format_path(config["server"]["listen"]["socket"])
APP_LISTEN=f"unix://{SOCK}"

job_state = {
    "job_state": "NONE",
    "job_id": "",
    "job_node": "",
    "job_url": ""
}
nginx_state = {
    "process": None
}
global_state = {
    "state": "STOPPED",
    "expected_job_id": ""
}

def write_nginx_config(server_configuration, job_configuration, nginx_fp):
    config_v4_listen = server_configuration["nginx"]["listen_v4"]
    config_v6_listen = server_configuration["nginx"]["listen_v6"]
    nginx_listen = format_path(server_configuration["nginx"]["listen"])
    nginx_pid = format_path(server_configuration["nginx"]["nginx_pid"])
    job_node = job_configuration["job_node"]
    output = f"""pid {nginx_pid};

events {{
	worker_connections 768;
	# multi_accept on;
}}

http {{
    sendfile on;
    tcp_nopush on;
    types_hash_max_size 2048;

    default_type application/octet-stream;

    gzip on;

    upstream kageauth {{
        server unix:{SOCK};
    }}

    server {{
        listen unix:{nginx_listen};
        server_name _;

        location / {{
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header Host $host;

            proxy_pass http://{job_node};

            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";

            auth_request /auth;
        }}
        location /auth {{
            internal;
            proxy_pass http://kageauth/api/session;
        }}
    }}
}}
    """

    nginx_fp.write(output)
    nginx_fp.flush()

# Need to be configurable to work with PBS
def get_job_state(job_id):
    state = subprocess.check_output(["sacct", "-o", "State", "-n", "-j", job_id]).decode("utf-8").replace(" ", "").split()
    if len(state) > 0:
        return state[0]

def get_job_node(job_id):
    node = subprocess.check_output(["sacct", "-o", "NodeList", "-n", "-j", job_id]).decode("utf-8").replace(" ", "").split()
    if len(node) > 0:
        return node[0]

def get_job_owner(job_id):
    user = subprocess.check_output(["sacct", "-o", "User", "-n", "-j", job_id]).decode("utf-8").replace(" ", "").split()
    if len(user) > 0:
        return user[0]

def cancel_job(job_id):
    subprocess.check_output(["scancel", job_id])

def get_ip_literal(job_node):
    # For now, assume that we have a hostname. Splitting by `:` will break IPv6 connectivity if an IPv6 literal is passed.
    node = job_node.split(":")
    return socket.gethostbyname(node[0])

def get_current_user():
    return getpass.getuser()

def validate_job_configuration(job_configuration):
    job_running = get_job_state(job_configuration["job_id"]) == "RUNNING"
    job_node = get_ip_literal(get_job_node(job_configuration["job_id"])) == get_ip_literal(job_configuration["job_node"])
    job_owner = get_job_owner(job_configuration["job_id"]) == get_current_user()

    return all([job_running, job_node, job_owner])

def queue_app(server_configuration):
    job_configuration_file_path = format_path(server_configuration["app"]["job_config"])
    job_id = subprocess.check_output(["sbatch", "--export", f"ALL,KAGE_JOB_CONFIG='{job_configuration_file_path}'", server_configuration["app"]["job_start"]]).decode("utf-8").split()[-1]
    return job_id

def start_nginx(server_configuration, job_configuration):
    # Assume that the job configuration is valid
    with open(format_path(server_configuration["nginx"]["nginx_config"]), "w") as nginx_fp:
        write_nginx_config(server_configuration, job_configuration, nginx_fp)
    
    # Assume that nginx is in PATH
    command = ["nginx", "-c", format_path(server_configuration["nginx"]["nginx_config"]), "-p", format_path(server_configuration["nginx"]["nginx_prefix"])]
    print("Running nginx: " + " ".join(command))
    process = subprocess.Popen(command)
    return process

def check_configuration_directories(server_configuration):
    prefix_dir = os.path.isdir(format_path(server_configuration["server"]["prefix"]))
    nginx_dir = os.path.isdir(format_path(server_configuration["nginx"]["nginx_prefix"]))
    nginx_log_dir = os.path.isdir(format_path(server_configuration["nginx"]["nginx_logs"]))

    return all([prefix_dir, nginx_dir, nginx_log_dir])

def create_configuration_directories(server_configuration):
    # Create prefix
    if not os.path.exists(format_path(server_configuration["server"]["prefix"])):
        os.makedirs(format_path(server_configuration["server"]["prefix"]))

    # Create nginx prefix
    if not os.path.exists(format_path(server_configuration["nginx"]["nginx_prefix"])):
        os.makedirs(format_path(server_configuration["nginx"]["nginx_prefix"]))

    if not os.path.exists(format_path(server_configuration["nginx"]["nginx_logs"])):
        os.makedirs(format_path(server_configuration["nginx"]["nginx_logs"]))

def update_job_configuration(server_configuration):
    global job_state 
    if os.path.exists(format_path(server_configuration["app"]["job_config"])):
        with open(format_path(server_configuration["app"]["job_config"]), "r") as config_fp:
            try:
                job_state = json.load(config_fp)
            except:
                print("Invalid job config format")
    else:
        job_state = {
            "job_state": "NONE",
            "job_id": "",
            "job_node": "",
            "job_url": ""
        }

def thread_check_job_running(delay=10):
    global sm
    while validate_job_configuration(job_state):
        print("Check job is still running")
        time.sleep(delay)
    print("Job has stopped")
    global_state["state"] = "STOPPED"
    global_state["expected_job_id"] = ""
    sm.invalidate_all() 

def can_start_nginx(server_configuration, job_configuration, expected_job_id):
    # Check that the job_configuration job_id matches the expected job id
    print("Checking if NGINX can be started...")
    print("Provided job ID: " + job_configuration["job_id"] + ". Expected job ID: " + expected_job_id)
    if job_configuration["job_id"] == expected_job_id:
        print("Expected value provided")
        return validate_job_configuration(job_configuration)
    else:
        return False

def nginx_get_pid(server_configuration):
    if not os.path.exists(format_path(server_configuration["nginx"]["nginx_pid"])):
        print("NGINX PIDfile does not exist")
        return

    nginx_pid = None
    with open(format_path(server_configuration["nginx"]["nginx_pid"])) as fp:
        nginx_pid = int(fp.read())
        print(f"Got PID: {nginx_pid}")

    if not psutil.pid_exists(nginx_pid):
        return

    nginx_process = psutil.Process(nginx_pid)
    if nginx_process.name() != 'nginx':
        return nginx_pid

def nginx_is_running(server_configuration):
    return nginx_get_pid(server_configuration)

def nginx_clear_socket(server_configuration):
    if not os.path.exists(format_path(server_configuration["nginx"]["listen"])):
        print("Socket path does not exist")
        return True

    os.remove(format_path(server_configuration["nginx"]["listen"]))

def nginx_stop(server_configuration):
    nginx_proc = nginx_get_pid(server_configuration)
    command = ["nginx", "-c", format_path(server_configuration["nginx"]["nginx_config"]), "-p", format_path(server_configuration["nginx"]["nginx_prefix"]), "-s", "stop"]
    process = subprocess.check_output(command)
    nginx_proc.kill()

    return process

def start_app(server_configuration):
    global global_state
    global nginx_state

    if config["web"]["session_cookie_name"] in request.cookies: # TODO: Cleanup
        print("Session token obtained")
        if sm.is_valid(request.cookies.get(config["web"]["session_cookie_name"])):
            pass
        else:
            print("Session invalid")
            return "Unauthorized", 401
    else:
        print("No session token provided")
        return "Unauthorized", 401
    # Reset global state
    print("Starting app...")
    print("Resetting job state.")
    global_state["state"] = "STOPPED"
    global_state["expected_job_id"] = ""

    # Firstly, check that config dirs exist
    print("Checking if config directories exist")
    if not check_configuration_directories(server_configuration):
        print("Config directories do not exist. Creating...")
        create_configuration_directories(server_configuration)
        print("Created config directories.")

    # Then, queue app
    print("Starting app...")
    job_id = queue_app(server_configuration)
    print(f"Job queued. Job ID is {job_id}")

    # Update global state 
    global_state["state"] = "QUEUED"
    global_state["expected_job_id"] = job_id
    
    # Wait for job to start
    print("Waiting for job to start...")
    while True:
        time.sleep(server_configuration["app"]["poll_time"]) 
        current_job_state = get_job_state(job_id)
        print(f"Current job state: {current_job_state}")
        if current_job_state != "PENDING":
            print("Job state updated!")
            if current_job_state == "FAILED":
                print("Job failed :(")
                return
            if current_job_state == "RUNNING":
                print("Job started!")
                break
    
    # Once the job has started, update the job config and validate
    print("Updating job configuration...")
    update_job_configuration(server_configuration)

    print("Checking if configuration is valid")
    await_config_end = datetime.datetime.now() + datetime.timedelta(0, server_configuration["app"]["job_start_timeout"])
    global_state["state"] = "STARTING"
    while (datetime.datetime.now() < await_config_end) and not validate_job_configuration(job_state):
        print("Waiting for job to provide a valid configuration...")
        update_job_configuration(server_configuration)
        time.sleep(server_configuration["app"]["poll_time"])

    if validate_job_configuration(job_state):
        # Job config is valid
        print("Job configuration is valid. Starting NGINX...")
        if can_start_nginx(server_configuration, job_state, job_id): # clean ts up ong 
            # Stop NGINX if it is running
            if nginx_is_running(server_configuration):
                nginx_stop(server_configuration)
            nginx_clear_socket(server_configuration)

            nginx_process = start_nginx(server_configuration, job_state)
            nginx_state["process"] = nginx_process
            global_state["state"] = "RUNNING"
            
            job_watchdog = threading.Thread(target=thread_check_job_running)
            job_watchdog.start()
        else:
            global_state["state"] = "FAILED"
    else:
        global_state["state"] = "TIMEOUT"
    

@app.route("/api/login", methods = ["POST"])
def login():
    # Check that the user is not already authenticated
    content = request.json
    # Validate required feilds
    for v in ["username", "password"]:
        if v not in content.keys():
            return "Bad request!", 400
    auth_result = au.check_password(content["username"], content["password"])
    
    if not auth_result:
        return "Unauthorized", 401
    else:
        remote_address = request.remote_addr # This will have to also check for the x-forwarded-for header to support reverse proxies
        session = sm.new_session(remote_address)
        return jsonify({'session-token': session})

@app.route("/api/session")
def session():
    # Check that the user's session cookie is valid
    if config["web"]["session_cookie_name"] in request.cookies:
        if sm.is_valid(request.cookies.get(config["web"]["session_cookie_name"])):
            return "OK", 200
    return "Unauthorized", 401

@app.route("/uapi/redirect")
def redirect():
    # Obtain the redirect information from the job
    if config["web"]["session_cookie_name"] in request.cookies: # TODO: Cleanup
        print("Session token obtained")
        if sm.is_valid(request.cookies.get(config["web"]["session_cookie_name"])):
            pass
        else:
            print("Session invalid")
            return "Unauthorized", 401
    else:
        print("No session token provided")
        return "Unauthorized", 401

    return jsonify(job_state)

@app.route("/uapi/api/start")
def start():
    start_app(config)
    return "OK", 200

@app.route("/uapi/api/state")
def state():
    if config["web"]["session_cookie_name"] in request.cookies: # TODO: Cleanup
        print("Session token obtained")
        if sm.is_valid(request.cookies.get(config["web"]["session_cookie_name"])):
            pass
        else:
            print("Session invalid")
            return "Unauthorized", 401
    else:
        print("No session token provided")
        return "Unauthorized", 401
    return jsonify(global_state)

if __name__ == "__main__":
    if nginx_is_running(config):
        nginx_stop(config)

    app.run(host=APP_LISTEN)
