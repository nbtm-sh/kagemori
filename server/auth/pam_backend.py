import pwd

def user_exists(username):
    try:
        pwd.getpwnam(username)
        return True
    except:
        return False

def get_user_uid(username):
    return pwd.getpwnam(username).pw_uid

def get_user_home(username):
    return pwd.getpwnam(username).pw_dir
