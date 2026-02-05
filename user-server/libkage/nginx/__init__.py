import libkage.dirs
import libkage.secure
import subprocess, os, psutil, logging
import kagemori_nginx

# TODO: As I'm under time pressure, I'm just going to turn this module into a wrapper around the new module to avoid re-writing large parts of the codebase

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
        self.instance = kagemori_nginx.KagemoriNGINX(
            nginx_configuration_path = self.dir_wrapper.format_path(nginx_prefix_path),
            kagemori_socket_file = self.dir_wrapper.format_path(local_socket),
            listen_socket = self.dir_wrapper.format_path(nginx_listen)
        )

    def _get_process_state(self):
        pass
    
    def _get_nginx_process(self):
        self.instance._update_nginx_state()
        return self.instance._nginx_pid
    
    def write_nginx_config(self):
        self.logger.debug(f"Writing NGINX configuration file.")
        self.instance.config.write_config()

    def start_nginx(self):
        self.instance.start()

    def stop_nginx(self):
        self.instance.stop()

    def add_server(self, server_name, enable_ssl = False, ssl_certificate_path = None):
        self.logger.debug(f"Creating new server {server_name}")
        self.instance.config.add_server(
            server_name = server_name,
            enable_ssl = enable_ssl,
            ssl_certificate = ssl_certificate_path
        )
        self.instance.config.write_config()
        self.logger.debug(f"Reloading NGINX...")
        self.instance.reload()
    
    def remove_server(self, server_name):
        self.logger.debug(f"Removing server {server_name}")
        self.instance.config.remove_server(server_name)
        self.instance.config.write_config()
        self.logger.debug(f"Reloading NGINX...")
        self.instance.reload()
