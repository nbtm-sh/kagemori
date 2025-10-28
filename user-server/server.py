import flask, os, socket, yaml, subprocess, getpass, json, time, threading, datetime, psutil, pathlib, pwd, grp, logging
import libkage.dirs, libkage.auth.pam_backend, libkage.session, libkage.secure, libkage.app, libkage.queue.slurm, libkage.nginx
from flask import request, jsonify, render_template, Response
from flask.globals import request_ctx

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

au = libkage.auth.pam_backend.AuthBackend()
dw = libkage.dirs.DirWrapper(au.username, au.uid)

# Load configuration
config = {}
POSSIBLE_CONFIG_PATH = [str(os.getenv('KAGE_CONFIG')), dw.format_path('./config.yaml'), dw.format_path('~/.config/kagemori/config.yaml')]
CONFIG_PATH = None
for c_path in POSSIBLE_CONFIG_PATH:
    if os.path.exists(c_path) and os.path.isfile(c_path):
        CONFIG_PATH = c_path
        break

if CONFIG_PATH == None:
    logger.critical(f"Cannot find configuration path in: " + ", ".join(POSSIBLE_CONFIG_PATH))
    exit(1)

logger.info(f"Loading configuration file {CONFIG_PATH}")

# Read and load the config file
with open(CONFIG_PATH, "r") as config_fp:
    try:
        config = yaml.safe_load(config_fp)
    except Exception as e:
        logger.critical("Unable to load configuration file {CONFIG_PATH}: {e}")

# Set configuration variables
dw.prefix = dw.format_path(config["kagemori"]["prefix"])

# Configure socket paths
APP_LISTEN="unix://" + dw.format_path(config["kagemori"]["listen"]["socket"])

# Set up objects
app = flask.Flask(__name__) # Flask app
cm = libkage.secure.SSL(
    dir_wrapper = dw,
    cert_expire_days = config["ssl"]["expire_days"],
    cert_key_length = config["ssl"]["key_length"],
    cert_country = config["ssl"]["identity"]["country"],
    cert_state = config["ssl"]["identity"]["state"],
    cert_city = config["ssl"]["identity"]["city"],
    cert_company = config["ssl"]["identity"]["company"],
    cert_company_section = config["ssl"]["identity"]["company_section"],
)
sm = libkage.session.SessionManager()
qm = libkage.queue.slurm.SlurmManager
ng = libkage.nginx.NGINXInstance(
    logger = logger,
    dir_wrapper = dw,
    cert_manager = cm,
    local_socket = config["kagemori"]["listen"]["socket"],
    nginx_listen = config["nginx"]["listen"]["socket"],
    nginx_prefix_path = config["nginx"]["prefix"],
    nginx_config_path = config["nginx"]["path"]["config"],
    nginx_log_path = config["nginx"]["path"]["logs"],
    nginx_pid_path = config["nginx"]["path"]["pid"],
    nginx_tmp_path = config["nginx"]["path"]["tmp"]
)

# Load applications
apps = []

for app_config in config["apps"]:
    append_app = libkage.app.App(
        path = app_config["project_root"],
        app_name = app_config["name"],
        queue_manager = qm,
        cert_manager = cm,
        dir_wrapper = dw,
        env_var_job_config_path = app_config["environment"]["config_file"],
        env_var_job_certificate_path = app_config["environment"]["ssl_cert"],
        env_var_job_key_path = app_config["environment"]["ssl_key"],
        env_var_job_domain_name = app_config["environment"]["domain_name"],
        job_configuration = None, # For now...
        username = au.username,
        job_start_timeout = app_config["queue"]["await_config_timeout"],
        job_start_poll_time = app_config["queue"]["starting_poll_interval"],
        job_running_poll_time = app_config["queue"]["running_poll_interval"],
        domain = app_config["domain"]
    )
    apps.append(append_app)
    logger.info(f"Registered app '{append_app.app_name}'!")

logger.info(f"Loaded with {len(apps)} registered app(s).")

@app.route("/api/login", methods=["POST"])
def login():
    # Validate that the keys exist
    request_content = request.json

    for k in ["username", "password"]:
        if k not in request_content.keys():
            logger.debug(f"{k} missing from login request.")
            return "Bad request", 400

    auth_check_password = au.check_password(request_content["username"], request_content["password"])
    if not auth_check_password:
        return "Unauthorised", 401

    remote_address = request.remote_addr
    username = request_content["username"]
    logger.info(f"Login request accepted from {username}")

    session = sm.new_session(remote_address)
    return jsonify({"session-token": session})

@app.route("/uapi/api/state")
def get_apps():
    if config["kagemori"]["cookie"] not in request.cookies:
        logger.debug(f"Missing session cookie")
        return "Unauthorised", 401

    if not sm.is_valid(request.cookies.get(config["kagemori"]["cookie"])):
        logger.debug(f"Invalid session cookie")
        return "Unauthorised", 401

    serial_return = [i.serialise() for i in apps]
    return jsonify(serial_return)

@app.route("/uapi/api/start")
def start():
    if config["kagemori"]["cookie"] not in request.cookies:
        logger.debug(f"Missing session cookie")
        return "Unauthorised", 401

    if not sm.is_valid(request.cookies.get(config["kagemori"]["cookie"])):
        logger.debug(f"Invalid session cookie")
        return "Unauthorised", 401
    
    # Check that the app name exists in the registered apps
    if "app" not in request.args.keys():
        logger.debug(f"Missing 'app' key")
        return "Bad request", 500

    # Check that app exists
    for app in apps:
        if app.app_name == request.args.get("app"):
            logger.debug(f"Starting app {app.app_name}")
            app.start()
            return "OK", 200
    logger.info(f"Failed to start app. Not found")
    return "Bad request", 500

@app.route("/api/session")
def session():
    logger.debug(dir(request_ctx))
    hostname = request_ctx.url_adapter.get_host('')
    logger.info(f"Got hostname {hostname}")

    # Find job associated with hostname
    # TODO: Make this faster
    resp = Response("")
    for app in apps:
        if app.domain == hostname:
            logger.debug(f"Found app {app.domain}")
            resp.headers["X-Kage-Forward"] = app.job_configuration["job_node"];
            resp.headers["X-Kage-SSL"] = os.path.join(app.job_state.job_tmp_directory, "cert.pem")
    return resp

@app.route("/uapi/api/setcookie")
def setcookie():
    # TODO: In future, this should be done with a local DB and a temporary one-time token that can be used to obtain the session information.
    # In it's current form, it would be possible to obtain session data from log files.
    return render_template("setcookie.html")

#@app.route("/uapi/redirect")
#def redirect():
#    if app_config["kagemori"]["cookie"] not in request.cookies:
#        logger.debug(f"Missing session cookie")
#        return "Unauthorised", 401
#
#    if not sm.is_valid(request.cookies.get(app_config["kagemori"]["cookie"])):
#        logger.debug(f"Invalid session cookie")
#        return "Unauthorised", 401
#    
#    # Check that the app name exists in the registered apps
#    if "app" not in request.args.keys():
#        logger.debug(f"Missing 'app' key")
#        return "Bad request", 500
#
#    # Check that app exists
#    for app in apps:
#        if app.app_name == request.args.get("app"):
#            logger.debug(f"Obtained redirect token")
#            app.start()
#            return "OK", 200
#    logger.info(f"Failed to start app. Not found")
#    return "Bad request", 500
#

if __name__ == "__main__":
    print(apps)
    print(apps[0].serialise())

    ng.write_nginx_config()
    ng.start_nginx()

    app.run(host=APP_LISTEN)
