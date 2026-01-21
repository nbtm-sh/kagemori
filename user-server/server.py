import flask, os, socket, yaml, subprocess, getpass, json, time, threading, datetime, psutil, pathlib, pwd, grp, logging, threading, re
import libkage.dirs, libkage.auth.pam_backend, libkage.session, libkage.secure, libkage.app, libkage.queue.slurm, libkage.nginx, libkage.cache
from flask import request, jsonify, render_template, Response, redirect, send_file
from flask.globals import request_ctx
import hashlib, sys

logger = None
au = None
dw = None
config = None
sc = None
cm = None
sm = None
qm = None
ng = None
apps = None
app = flask.Flask(__name__) # Flask app

APP_LISTEN = None

def main_load(reload_auth=True):
    global app
    global logger
    global au
    global dw
    global config
    global sc
    global cm
    global sm
    global qm
    global ng
    global apps
    global APP_LISTEN

    VERSION="0.4rc1"

    logging.basicConfig()
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    logger.info(f"kagemori user-server {VERSION}")
    logger.info(f"git: https://github.com/nbtm-sh/kagemori")
    logger.info(f"contact: z3545907@ad.unsw.edu.au")

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

    # Configure logging
    if not os.path.isdir(dw.format_path(config["kagemori"]["logging"]["path"])):
        os.makedirs(dw.format_path(config["kagemori"]["logging"]["path"]))

    logging_file_handler = logging.FileHandler("{0}/{1}.log".format(dw.format_path(config["kagemori"]["logging"]["path"]), "kagemori"))
    logging_formatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
    logging_file_handler.setFormatter(logging_formatter)
    logger.addHandler(logging_file_handler)

    if config["kagemori"]["logging"]["debug"]:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # Configure state cache
    sc = None
    if config["kagemori"]["state_cache"]["use_state_cache"]:
        sc = libkage.cache.StateCache(
            dw.format_path(config["kagemori"]["state_cache"]["state_cache_file"])
        )
        sc.load_cache()
    else:
        logger.warn("State cache is disabled. Jobs will be lost between user-server restarts.")

    # Set configuration variables
    dw.prefix = dw.format_path(config["kagemori"]["prefix"])

    # Configure socket paths
    APP_LISTEN="unix://" + dw.format_path(config["kagemori"]["listen"]["socket"])

    # Set up objects
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
    if reload_auth:
        sm = libkage.session.SessionManager()
    qm = libkage.queue.slurm.SlurmManager
    ng = libkage.nginx.NGINXInstance(
        logger = logger,
        dir_wrapper = dw,
        cert_manager = cm,
        local_socket = config["kagemori"]["listen"]["socket"],
        nginx_listen = config["nginx"]["listen"]["socket"],
        nginx_prefix_path = config["nginx"]["prefix"],
        nginx_config_path = os.path.join(config["nginx"]["prefix"], config["nginx"]["path"]["config"]),
        nginx_log_path = os.path.join(config["nginx"]["prefix"], config["nginx"]["path"]["logs"]),
        nginx_pid_path = os.path.join(config["nginx"]["prefix"], config["nginx"]["path"]["pid"]),
        nginx_tmp_path = os.path.join(config["nginx"]["prefix"], config["nginx"]["path"]["tmp"])
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
            domain = app_config["domain"],
            state_cache = sc
        )
        apps.append(append_app)
        logger.info(f"Registered app '{append_app.app_name}'!")

    logger.info(f"Loaded with {len(apps)} registered app(s).")

    def _thread_set_socket_permissions(paths):
        logger.info("Started thread to set permissions on the socket files")
        time.sleep(1)
        for path in paths:
            logger.info(f"Set permission on {path}")
            os.chmod(path, 0o777)

    paths_to_create = [
        dw.format_path(config["nginx"]["prefix"]),
        os.path.join(dw.format_path(config["nginx"]["prefix"]), "logs"),
        os.path.join(dw.format_path(config["nginx"]["prefix"]), "tmp"),
        os.path.dirname(dw.format_path(config["nginx"]["listen"]["socket"])),
        os.path.dirname(dw.format_path(config["kagemori"]["listen"]["socket"])),
    ]

    for check_path in paths_to_create:
        logger.debug(f"Checking directory {check_path}")
        if not os.path.isdir(check_path):
            logger.info(f"Creating directory {check_path}")
            os.makedirs(check_path)

    ng.write_nginx_config()
    if ng._get_nginx_process():
        logger.info("NGINX is already running! Stopping...")
        ng.stop_nginx()

    ng.start_nginx()

    # Start the thread to set the permissions on the socket
    permission_thread = threading.Thread(target=_thread_set_socket_permissions, args=([dw.format_path(config["kagemori"]["listen"]["socket"]), dw.format_path(config["nginx"]["listen"]["socket"])],))
    permission_thread.start()


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
    state_hash = hashlib.sha256(bytes(json.dumps(serial_return), "UTF-8")).hexdigest()
    serial_return = {"hash": state_hash, "data": serial_return}
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

@app.route("/uapi/api/stop")
def stop():
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

    for app in apps:
        if app.app_name == request.args.get("app"):
            app.stop()
            return "OK", 200
    return "Bad request", 500


@app.route("/api/session")
def session():
    hostname = request_ctx.url_adapter.get_host('')
    logger.info(f"Got hostname {hostname}")

    # Find job associated with hostname
    # TODO: Make this faster
    resp = Response("")
    for app in apps:
        if app.domain == hostname:
            logger.debug(f"Found app {app.domain}")
            if app.job_configuration is not None:
                resp.headers["X-Kage-Forward"] = app.job_configuration["job_node"];
                resp.headers["X-Kage-SSL"] = os.path.join(app.job_state.job_tmp_directory, "cert.pem")
    return resp

@app.route("/uapi/api/reload")
def reload():
    main_load(reload_auth=False)
    return redirect("/kagemori/mapi/uri/login")

@app.route("/uapi/api/forget-state")
def forget_state():
    main_load(reload_auth=False)
    return redirect("/kagemori/mapi/uri/login")

@app.route("/uapi/api/attach")
def attach():
    # TODO: This feels pretty sketchy. Might be worth seeing if theres a better way to do this
    # Might also be worth doing some permissions checking to make sure the file being loaded is owned by the correct user and has 600 perms
    if config["kagemori"]["cookie"] not in request.cookies:
        logger.debug(f"Missing session cookie")
        return "Unauthorised", 401

    if not sm.is_valid(request.cookies.get(config["kagemori"]["cookie"])):
        logger.debug(f"Invalid session cookie")
        return "Unauthorised", 401

    job_uuid = request.args.get("uuid")
    reg = re.compile('^[a-f0-9]{8}-?[a-f0-9]{4}-?4[a-f0-9]{3}-?[89ab][a-f0-9]{3}-?[a-f0-9]{12}\Z', re.I)
    if not reg.match(job_uuid):
        logger.info(f"Unable to attach. Invalid UUID")
        return "Bad request", 401

    app_name = request.args.get("app")
    
    find_app = [i for i in apps if i.app_name == app_name]
    if len(find_app) == 0:
        logger.info(f"Unable to attach. Invalid app name")
        return "Bad request", 401
    
    sc.set_config(app_name, job_uuid) 
    find_app[0].resume()
    return redirect("/kagemori/mapi/uri/login")

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
    main_load()
    try:
        app.run(host=APP_LISTEN)
    except KeyboardInterrupt:
        logger.info(f"got interrupt. saving state...")
        if sc:
            sc.write_cache()
        logger.info(f"see you next time~")

        try:
            sys.exit(130)
        except SystemExit:
            os._exit(130)
