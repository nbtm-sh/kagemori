import libkage.queue.state
import os, json, time, datetime, uuid, logging, threading

class App:
    START_SCRIPT = "start.sh"
    APP_CONFIG="config.json"
    KEY_REQUEST_STATE = "request_state"
    JOB_CONFIG_EXPECTED_KEYS = ["job_id", "job_node", "job_url"]

    def __init__(self, path, app_name, queue_manager, cert_manager, dir_wrapper, env_var_job_config_path=None, env_var_job_certificate_path=None, env_var_job_key_path=None, job_configuration=None, username=None, job_start_timeout=None, job_start_poll_time=None, job_running_poll_time=None, domain=None, env_var_job_domain_name=None):
        self.path = path
        self.app_name = app_name
        self.queue_manager = queue_manager
        self.job_state = libkage.queue.state.JobState() 
        self.cert_manager = cert_manager
        self.dir_wrapper = dir_wrapper
        self.job_configuration = job_configuration
        self.job_start_timeout = job_start_timeout
        self.job_start_poll_time = job_start_poll_time
        self.job_running_poll_time = job_running_poll_time
        self.username = username
        self.logger = logging.getLogger()
        self.domain = domain
        self.check_configuration_thread = None
        self.lock = False

        # Environment variables
        self.env_var_job_config_path = env_var_job_config_path
        self.env_var_job_certificate_path = env_var_job_certificate_path
        self.env_var_job_key_path = env_var_job_key_path
        self.env_var_job_domain_name = env_var_job_domain_name

    @staticmethod
    def load_configuration(config, username=None, queue_manager=None, cert_manager=None, dir_wrapper=None):
        return App(
            app_name=config["name"],
            path=config["project_root"],
            job_start_timeout=config["queue"]["await_config_timeout"],
            job_start_poll_time=config["queue"]["starting_poll_interval"],
            job_running_poll_time=config["queue"]["running_poll_interval"]
        )

    @staticmethod
    def _thread_check_job_state(self):
        while True:
            self.logger.debug(f"_thread_check_job_state thread waiting {self.job_running_poll_time}")
            time.sleep(self.job_running_poll_time)

            self.update_job_state()
            self.logger.debug(self.job_configuration)

            if App.KEY_REQUEST_STATE in self.job_configuration.keys():
                if self.job_configuration[App.KEY_REQUEST_STATE] == "STOP":
                    self.logger.info(f"Job {self.job_state.job_uuid} requested stop")
                    self.stop()

            if self.job_state.job_state != "RUNNING":
                break

        # Reset the job state
        self.clean_state()

    def clean_state(self):
        self.logger.debug("Cleaning job states...")
        self.job_state = libkage.queue.state.JobState()
        self.job_configuration = None
        self.lock = False

    def serialise(self):
        return {
            "app_name": self.app_name,
            "path": self.path,
            "state": self.job_state.serialise(),
            "config": self.job_configuration,
            "domain": self.domain
        }

    def update_job_configuration(self):
        config_path = os.path.join(self.job_state.job_tmp_directory, App.APP_CONFIG)
        self.logger.debug(f"Check config_path: {config_path}. Exists: {os.path.exists(config_path)}")
        if os.path.exists(config_path):
            with open(config_path, "r") as config_fp:
                self.logger.debug(f"Reading {config_path}")
                try:
                    self.job_configuration = json.load(config_fp)
                except:
                    self.logger.warn(f"Configuration file invalid") 
                    # Job configuration is invalid
    
    def is_configuration_valid(self):
        # Check if the information provided by the job is valid
        # Is all the info there?
        if self.job_configuration is None:
            return False

        check_keys = all([k in self.job_configuration.keys() for k in App.JOB_CONFIG_EXPECTED_KEYS])
        if not check_keys:
            return False

        # Check the job ID matches
        if self.job_state.job_id != self.job_configuration["job_id"]:
            return False

        # Check that the job owner matches
        if self.queue_manager.get_job_owner(self.job_state.job_id) != self.username:
            return False

        # Check that the nodes match
        if self.queue_manager.get_ip_literal(self.job_state.job_node) != self.queue_manager.get_ip_literal(self.job_configuration["job_node"]):
            return False
        
        # All checks have passed
        return True
        
    def update_job_state(self):
        self.job_state.job_state = self.queue_manager.get_job_state(self.job_state.job_id)
        self.job_state.job_owner = self.queue_manager.get_job_owner(self.job_state.job_id)
        self.job_state.job_node = self.queue_manager.get_job_node(self.job_state.job_id)
        self.job_state.end_date = self.queue_manager.end_time(self.job_state.job_id)
        self.logger.debug(f"Job config: job_state: {self.job_state.job_state}, job_owner: {self.job_state.job_owner}, job_node: {self.job_state.job_node}")
        #self.job_state = self.queue_manager.get_job_state(self.job_state.job_id)
        self.update_job_configuration()

    def start(self):
        # Check that no job is already running
        if self.lock: 
            self.logger.info(f"Job is already running. Will not start another!")
            return True

        self.lock = True

        # Generate job UUID
        self.job_state.job_uuid = str(uuid.uuid4())
        self.logger.info(f"Starting new job. UUID: {self.job_state.job_uuid}")
        
        # Create job directory and generate certificates
        self.job_state.job_tmp_directory = self.dir_wrapper.create_temporary_job_dir(self.job_state.job_uuid)
        self.job_state.job_certificate = self.cert_manager.create_certificate(self.job_state.job_uuid)
        self.logger.debug(f"Job temp directory: {self.job_state.job_tmp_directory}")
        self.logger.debug(f"Job cert: {self.job_state.job_certificate}")

        self.job_state.gui_state = "SECURE"

        # Configure environment variables
        start_script = os.path.join(self.path, App.START_SCRIPT)
        self.logger.debug(f"Start script: {start_script}")
        config_path = os.path.join(self.job_state.job_tmp_directory, App.APP_CONFIG)
        self.logger.debug(f"Config path: {config_path}")

        # Start job
        self.job_state.job_id = self.queue_manager.submit_job(start_script, **{ # Exports
            self.env_var_job_config_path: config_path,
            self.env_var_job_certificate_path: self.job_state.job_certificate.cert_out_path,
            self.env_var_job_key_path: self.job_state.job_certificate.cert_key_path,
            self.env_var_job_domain_name: self.domain
        }) # End exports
        self.job_state.gui_state = "RESOURCE"

        self.update_job_state()
        # Await the job's resource allocation
        self.logger.debug("Logic check await resource loop: " + str(bool(self.job_state.job_state) and (self.job_state.job_state != "RUNNING" or self.job_state.job_state != "FAILED")))
        self.logger.debug("bool(job_state): " + str(bool(self.job_state.job_state)))
        self.logger.debug("bool(job_state != 'RUNNING'): " + str(bool(self.job_state.job_state != "RUNNING")))
        self.logger.debug("bool(job_state != 'FAILED'): " + str(bool(self.job_state.job_state != "FAILED")))
        # Await for assignment
        while not bool(self.job_state.job_state):
            self.update_job_state()
            time.sleep(self.job_start_poll_time)
            self.logger.debug(f"Update job state in await assignment loop")

        self.job_state.gui_state = "STARTED"
        self.logger.debug("Logic check await resource loop: " + str(bool(self.job_state.job_state) and (self.job_state.job_state != "RUNNING" and self.job_state.job_state != "FAILED")))
        self.logger.debug("bool(job_state): " + str(bool(self.job_state.job_state)))
        self.logger.debug("bool(job_state != 'RUNNING'): " + str(bool(self.job_state.job_state != "RUNNING")))
        self.logger.debug("bool(job_state != 'FAILED'): " + str(bool(self.job_state.job_state != "FAILED")))
        # Await the job's resource allocation
        while bool(self.job_state.job_state) and (self.job_state.job_state != "RUNNING" and self.job_state.job_state != "FAILED"):
            self.logger.debug(f"Update job state in await resource loop")
            self.update_job_state()
            time.sleep(self.job_start_poll_time)

        if self.job_state.job_state == "FAILED":
            self.logger.debug(f"Job failed")
            self.job_state.gui_state = "FAILED" 
            return False

        self.job_state.gui_state = "CONFIG" 
        # Start job with a timeout
        timeout = datetime.datetime.now() + datetime.timedelta(0, self.job_start_timeout)
        self.logger.debug(f"Timeout in {timeout}")
        while datetime.datetime.now() < timeout: 
            self.logger.debug(f"Update job_state in await start loop")
            self.update_job_state()
            if self.is_configuration_valid():
                break
            time.sleep(self.job_start_poll_time)

        if not self.is_configuration_valid():
            self.stop()
            return False

        if datetime.datetime.now() >= timeout:
            # Kill the job if it has timed out
            self.stop()
            return False

        self.job_state.gui_state = "READY" 
        self.check_configuration_thread = threading.Thread(target=App._thread_check_job_state, args=(self,))
        self.check_configuration_thread.start()

        return True

    def stop(self):
        self.queue_manager.cancel_job(self.job_state.job_id)
        self.lock = False

    def session(self):
        if self.job_state.state == "RUNNING":
            return {
                "target": self.job_configuration["job_node"],
                "cert": self.job_state.job_certificate.cert_out_path,
                "error": None
            }
        else:
            return {
                "error": "Invalid"
            }

    def status(self):
        job_conf = self.job_state.serialise()
        job_conf["job_configuration"] = self.job_configuration
