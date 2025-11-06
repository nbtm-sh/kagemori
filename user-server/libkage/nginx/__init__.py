import libkage.dirs
import libkage.secure
import subprocess, os, psutil, logging

class NGINXConfig:
    def __init__(self,
            listen,
            prefix_path,
            config_path,
            log_path,
            pid_path,
            tmp_path):
        self.listen = listen
        self.prefix_path = prefix_path
        self.config_path = config_path
        self.log_path = log_path
        self.pid_path = pid_path
        self.tmp_path = tmp_path

class NGINXInstance:
    # Consts
    PROC_STATE_RUNNING = "RUNNING"
    PROC_STATE_STOPPED = "STOPPED"

    def __init__(self, logger, dir_wrapper : libkage.dirs.DirWrapper, cert_manager : libkage.secure.SSL, local_socket, nginx_listen, nginx_prefix_path, nginx_config_path, nginx_log_path, nginx_pid_path, nginx_tmp_path):
        self.logger = logger
        self.dir_wrapper = dir_wrapper
        self.cert_manager = cert_manager
        self.local_socket = self.dir_wrapper.format_path(local_socket)
        self.config = NGINXConfig(
            self.dir_wrapper.format_path(nginx_listen),
            self.dir_wrapper.format_path(nginx_prefix_path),
            self.dir_wrapper.format_path(nginx_config_path),
            self.dir_wrapper.format_path(nginx_log_path),
            self.dir_wrapper.format_path(nginx_pid_path),
            self.dir_wrapper.format_path(nginx_tmp_path)
        )

    def _get_process_state(self):
        pass
    
    def _get_nginx_process(self):
        if not os.path.exists(self.config.pid_path):
            return None
        
        nginx_pid = None
        with open(self.config.pid_path, "r") as fp:
            nginx_pid = int(fp.read())

        try:
            nginx_process = psutil.Process(nginx_pid)
            if nginx_process.name() == "nginx":
                return nginx_process
        except:
            return False
    
    def write_nginx_config(self):
        self.logger.info(f"Writing NGINX configuration to {self.config.config_path}")

        with open(os.path.join(self.config.prefix_path, self.config.config_path), "w") as fp:
            fp.write(f"pid {self.config.pid_path};\n")
            fp.write(f"error_log {self.config.log_path}/error.log;\n")
            fp.write(f"\n")
            fp.write(f"events {{\n")
            fp.write(f"    worker_connections 768;\n")
            fp.write(f"}}\n")
            fp.write(f"\n")
            fp.write(f"http {{\n")
            fp.write(f"    sendfile on;\n")
            #fp.write(f"    tpu_nopush on;\n")
            fp.write(f"    types_hash_max_size 2048;\n")
            fp.write(f"\n")
            fp.write(f"    client_body_temp_path {self.config.tmp_path}/client_body;\n")
            fp.write(f"    proxy_temp_path {self.config.tmp_path}/proxy;\n")
            fp.write(f"    fastcgi_temp_path {self.config.tmp_path}/fastcgi;\n")
            fp.write(f"    uwsgi_temp_path {self.config.tmp_path}/uwsgi;\n")
            fp.write(f"    scgi_temp_path {self.config.tmp_path}/scgi;\n")
            fp.write(f"\n")
            fp.write(f"    default_type application/octet-stream;\n")
            fp.write(f"\n")
            fp.write(f"    gzip on;\n")
            fp.write(f"\n")
            fp.write(f"    upstream kageauth {{\n")
            fp.write(f"        server unix:{self.local_socket}; \n")
            fp.write(f"    }}\n")
            fp.write(f"\n")
            fp.write(f"    server {{\n")
            fp.write(f"        listen unix:{self.config.listen};\n")
            fp.write(f"        resolver 129.94.0.196;\n")
            fp.write(f"        server_name _;\n")
            fp.write(f"\n")
            fp.write(f"        access_log {self.config.log_path}/access.log;\n")
            fp.write(f"\n")
            fp.write(f"        location / {{\n")
            fp.write(f"            auth_request /auth;\n")
            fp.write(f"            auth_request_set $kagemori_proxy_target $upstream_http_x_kage_forward;\n")
            fp.write(f"            auth_request_set $kagemori_ssl_cert $upstream_http_x_kage_ssl;\n")
            fp.write(f"\n")
            fp.write(f"            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n")
            fp.write(f"            proxy_set_header Host $host;\n")
            #fp.write(f"            proxy_ssl_verify on;\n")
            #fp.write(f"            proxy_ssl_verify_depth 1;\n")
            #fp.write(f"            proxy_ssl_trusted_certificate $kagemori_ssl_cert;\n")
            fp.write(f"            \n")
            fp.write(f"            proxy_pass http://$kagemori_proxy_target;\n")
            fp.write(f"\n")
            fp.write(f"            proxy_http_version 1.1;\n")
            fp.write(f"            proxy_set_header Upgrade $http_upgrade;\n")
            fp.write(f"            proxy_set_header Connection \"upgrade\";\n")
            fp.write(f"            proxy_set_header Sec-WebSocket-Key $http_sec_websocket_key;\n")
            fp.write(f"            proxy_set_header Sec-WebSocket-Version $http_sec_websocket_version;\n")
            fp.write(f"            proxy_set_header Sec-WebSocket-Extensions $http_sec_websocket_extensions;\n")
            fp.write(f"            proxy_read_timeout 86400s;\n")
            fp.write(f"            proxy_send_timeout 86400s;\n")
            fp.write(f"        }}\n")
            fp.write(f"        location /auth {{\n")
            fp.write(f"            internal;\n")
            fp.write(f"            proxy_pass http://kageauth/api/session;\n")
            fp.write(f"\n")
            fp.write(f"            proxy_set_header Host $host;\n")
            fp.write(f"            proxy_set_header X-Original-URI $request_uri;\n")
            fp.write(f"            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n")
            fp.write(f"            proxy_set_header X-Forwarded-Proto $scheme;\n")
            fp.write(f"        }}\n")
            fp.write(f"    }}\n")
            fp.write(f"}}\n")

    def start_nginx(self):
        command = ["nginx", "-c", self.config.config_path, "-p", self.config.prefix_path]
        self.logger.info(f"Starting NGINX... {command}") 
        process = subprocess.Popen(command)
        return process

    def stop_nginx(self):
        nginx_process = self._get_nginx_process()
        command = ["nginx", "-c", self.config.config_path, "-p", self.config.prefix_path, "-s", "quit"]
        process = subprocess.check_output(command)
        nginx_process.kill()
        return process
