import getpass
import pam

class AuthBackend:
    def __init__(self, service="login"):
        self.username = getpass.getuser()
        self.service = service

    def check_password(self, username, password):
        # Do not touch PAM if the username provided is not correct
        if username != self.username:
            return False
        p = pam.pam()
        return p.authenticate(self.username, password)
