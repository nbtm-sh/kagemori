import auth.pam_backend

def format_path(username, path):
    string_map = {
        "%i": str(auth.pam_backend.get_user_uid(username)),
        "%u": username,
        "%h": auth.pam_backend.get_user_home(username)
    }

    for k, v in string_map.items():
        path = path.replace(k, v)
    
    return path
