import yaml
import logging

class StateCache:
    def __init__(self, cache_path):
        self.cache_path = cache_path
        self.running_jobs = {}
        self.logger = logging.getLogger()

        # File is formatted as such
        # apps:
        #   cryosparc: job-6377b850-3219-4c27-836b-fe2648b380e3
        #   sdesktop: job-8782699f-e6ad-46a7-8cd7-9a4cef9a7db2

    def get_config(self, app_name):
        """ Used to obtain an existing job state for an application. Returns None if no existing state is found """

        self.logger.debug(f"Attempting to find existing job state for {app_name}")

        if app_name in self.running_jobs.keys():
            self.logger.debug(f"Found existing job state for {app_name} {self.running_jobs[app_name]}")
            return self.running_jobs[app_name]

        self.logger.warn(f"Could not get job state for {app_name}. No existing job state for {app_name} exists!")

    def set_config(self, app_name, job_id):
        """ Set the job ID for the app_name """

        self.logger.debug(f"Setting job state for {app_name}. Job ID: {job_id}")
        self.running_jobs[app_name] = job_id

        self.write_cache()

    def clear_config(self, app_name):
        """ Clear a job state when an application has exited """

        self.logger.debug(f"Attempting to clear job state for {app_name}...")

        if self.running_jobs.pop(app_name, None):
            # Will return None if the key does not exist
            self.logger.info(f"Cleared job state for {app_name}")
            self.write_cache()

            return

        self.logger.warn(f"Could not clear job state for {app_name}. No existing job state was found!")

    def write_cache(self):
        """ Write the current job states to the cache file """

        self.logger.debug(f"Attempting to write job state cache to {self.cache_path}...")

        try:
            with open(self.cache_path, "w") as cache_fp:
                yaml.dump({"apps": self.running_jobs}, cache_fp, default_flow_style=False)
            self.logger.info(f"Wrote {len(self.running_jobs)} job state(s) to state cache file ({self.cache_path})!")
        except Exception as e:
            self.logger.critical("Unable to write to state cache file ({self.cache_path})! {e}")

    def load_cache(self):
        try:
            self.logger.info(f"Attempting to read cache file {self.cache_path}")

            with open(self.cache_path, "r") as cache_fp:
                self.running_jobs = yaml.safe_load(cache_fp)["apps"]

            self.logger.debug(f"Read cache file. {len(self.running_jobs)} cached services")
        except Exception as e:
            # Just return, since this file is only used for resuming after a restart
            self.logger.warn(f"Failed to read state cache file {self.cache_path}: {e}")
