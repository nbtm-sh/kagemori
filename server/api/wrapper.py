import requests_unixsocket, json, urllib.parse

class UserDaemon:
    @staticmethod
    def login(socket, username, password):
        session = requests_unixsocket.Session()
        url = urllib.parse.quote_plus(socket)
        
        response = session.post(f"http+unix://{url}/api/login", json={"username": username, "password": password})
        return response.json() if response.status_code == 200 else None
    
    @staticmethod
    def start(socket):
        session = requests_unixsocket.Session()
        url = urllib.parse.quote_plus(socket)
        
        response = session.get(f"http+unix://{url}/api/start")
        return response.status_code == 200
    
    @staticmethod
    def state(socket):
        session = requests_unixsocket.Session()
        url = urllib.parse.quote_plus(socket)
        
        response = session.get(f"http+unix://{url}/api/state")
        return response.json() if response.status_code == 200 else None
