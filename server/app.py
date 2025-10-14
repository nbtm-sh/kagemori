from flask import Flask, request, jsonify, render_template, Response, make_response
import auth.path, auth.pam_backend, api.wrapper, session.session_mapper
import yaml, git
app = Flask(__name__)

config = {}
with open("./config.yaml", "r") as config_fp:
    config = yaml.safe_load(config_fp)

repo = git.Repo(search_parent_directories=True)
project_sha = repo.head.object.hexsha[:7]
project_branch = repo.active_branch.name
print(dir(repo.head.object))

# Set up session mapper
smapper = session.session_mapper.SessionMapManager()

@app.route("/mapi/login", methods = ['POST'])
def login():
    # Validate required feilds 
    for v in ["username", "password"]:
        if v not in request.json.keys():
            return make_response(jsonify({"error": "Bad request"}), 400)

    # Check that the user exists
    user_exists = auth.pam_backend.user_exists(request.json["username"])
    if not user_exists:
        return make_response(jsonify({"error": "Invalid username or password"}), 401)
    # TODO: Implement min/max UID/GID constraints
    
    # Get path to user daemon unix socket
    user_socket = auth.path.format_path(request.json["username"], config["server"]["user_socket"])
    nginx_socket = auth.path.format_path(request.json["username"], config["server"]["nginx_socket"])

    # TODO: Validate file permissions on socket before sending username and password
    # Perform login
    try:
        login_response = api.wrapper.UserDaemon.login(user_socket, request.json["username"], request.json["password"])
    except:
        return make_response(jsonify({"error": "Unable to connect to the userland daemon socket. Is the daemon running?"}), 500)
    if login_response is None:
        return make_response(jsonify({"error": "Invalid username or password"}), 401)

    # Map session
    # TODO: Obtain remote address
    session = smapper.new_session_map(
        session_token = login_response["session-token"],
        mapped_socket = user_socket,
        mapped_nginx_socket = nginx_socket
    )

    return jsonify(login_response)

@app.route("/mapi/whois")
def whois():
    token = request.args.get("token")
    valid = smapper.is_valid(token, '::1')
    if valid is None:
        return jsonify({})
    
    return jsonify({"socket": valid.mapped_socket})

@app.route("/mapi/session")
def session():
    # Check that a session token is provided
    if not config["web"]["session_cookie_name"] in request.cookies:
        return "Unauthorized", 401

    session_token = request.cookies[config["web"]["session_cookie_name"]]
    valid = smapper.is_valid(session_token)
    if valid is None:
        return "Unauthorized", 401

    resp = Response("")
    resp.headers["X-Kage-Forward"] = valid.mapped_socket
    resp.headers["X-Kage-NGINX"] = valid.mapped_nginx_socket
    return resp

@app.route("/mapi/uri/login")
def login_form():
    return render_template("login.html",
        username_placeholder = config["branding"]["username_placeholder"],
        password_placeholder = config["branding"]["password_placeholder"],
        git_hash = project_sha,
        git_branch = project_branch
    )

if __name__ == "__main__":
    app.run(host="::", port="3621")
