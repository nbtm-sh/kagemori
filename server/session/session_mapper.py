import datetime, hashlib

class SessionMap:
    def __init__(self, remote_address='::1', session_token_hash='', session_lifetime=datetime.timedelta(0,43200), mapped_socket=None, mapped_nginx_socket=None):
        self.remote_address = remote_address
        self.session_token_hash = session_token_hash
        self.session_lifetime = session_lifetime
        self.session_expire = datetime.datetime.now() + session_lifetime
        self.mapped_socket = mapped_socket # Path to userland daemon UNIX domain socket
        self.mapped_nginx_socket = mapped_nginx_socket

    @staticmethod
    def get_hash(token, hash_method=hashlib.sha512, encoding="UTF-8"):
        token_bytes = bytes(token, encoding)
        return hash_method(token_bytes).hexdigest()
    
    @property
    def is_valid(self):
        return self.session_expire > datetime.datetime.now()

    def update_session(self, remote_address):
        self.session_expire = datetime.datetime.now() + self.session_lifetime
        self.remote_address = remote_address

class SessionMapManager:
    def __init__(self, hash_method=hashlib.sha512, encoding="UTF-8"):
        self.sessions = []
        self.hash_method = hash_method
        self.encoding = encoding

    # TODO: Can be optimised with a hashmap
    def _find_session(self, session_token_hash):
        for i in self.sessions:
            if i.session_token_hash == session_token_hash:
                return i
        return None
    # TODO: Can be optimised with a hashmap
    def _find_session_index(self, session_token_hash):
        for i in range(len(self.sessions)):
            if self.sessions[i].session_token_hash == session_token_hash:
                return i
        return None
    
    def is_valid(self, session_token, remote_address='::1'):
        session_token_hash = SessionMap.get_hash(session_token, hash_method=self.hash_method, encoding=self.encoding)
        session_object = self._find_session(session_token_hash)
        is_valid = session_object.is_valid if session_object is not None else False

        if not is_valid:
            return None

        session_object.update_session(remote_address)
        return session_object
    
    def new_session_map(self, remote_address='::1', session_token='', mapped_socket='', mapped_nginx_socket='', lifetime=datetime.timedelta(0,43200)):
        # TODO: Ideally, the lifetime value should be provided by the userland daemon
        # with a max value capped in the privileged proxy service

        session_object = SessionMap(
            remote_address = remote_address,
            session_token_hash = SessionMap.get_hash(session_token, hash_method=self.hash_method, encoding=self.encoding),
            session_lifetime = lifetime,
            mapped_socket = mapped_socket,
            mapped_nginx_socket = mapped_nginx_socket
        )
        self.sessions.append(session_object)
        return session_object
