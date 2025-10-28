import string, random, datetime

class Session:
    SESSION_TYPE_USER = "USER"
    SESSION_TYPE_JOB = "JOB"
    def __init__(self, remote_address='::1', session_token='', session_lifetime=datetime.timedelta(0,43200), session_type=SESSION_TYPE_USER, mapped_app=None):
        self.remote_address = remote_address
        self.session_token = session_token
        self.session_expire = datetime.datetime.now() + session_lifetime 
        self.session_lifetime = session_lifetime
        self.last_access = None
        self.session_type = session_type
        self.mapped_app = None
    
    @staticmethod
    def generate_session_token(length=128):
        pool = string.printable[:62]
        return ''.join([random.choice(pool) for i in range(length)]) 

    @property
    def is_valid(self, mapped_app=None):
        if mapped_app is not None:
            self.mapped_app = mapped_app

        return self.session_expire > datetime.datetime.now()

    def update_session(self, remote_address):
        self.session_expire = datetime.datetime.now() + self.session_lifetime
        self.remote_address = remote_address

class SessionManager:
    def __init__(self):
        self.sessions = []

    def _find_session(self, session_token):
        for i in self.sessions:
            if i.session_token == session_token:
                return i
        return None

    def _find_session_index(self, session_token):
        for i in range(len(self.sessions)):
            if self.sessions[i].session_token == session_token:
                return i 
        return None

    def remove_session(self, session_token):
        session_token_index = self._find_session_index(session_token)
        if session_token is not None:
            self.sessions.remove(session_token_index)
    
    def is_valid(self, session_token, remote_address='::1', mapped_app=None):
        session_object = self._find_session(session_token)
        if session_object is not None:
            if session_object.is_valid:
                session_object.update_session(remote_address)
                return True
            else:
                self.remove_session(session_token)
        return False

    def invalidate_all(self):
        self.sessions = []
    
    def new_session(self, remote_address='::1', length=128, lifetime=datetime.timedelta(0,43200), mapped_app=None):
        while True:
            session_token = Session.generate_session_token(length)
            # Check that this session token is not in use
            if not self.is_valid(session_token, remote_address):
                break
        session_object = Session(
            remote_address = remote_address,
            session_token  = session_token,
            mapped_app = mapped_app
        )
        self.sessions.append(session_object) 
        return session_token 
