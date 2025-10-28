class JobState:
    def __init__(self, job_id=None, job_state=None, job_tmp_directory=None, job_uuid=None, job_certificate=None, job_owner=None, job_node=None, gui_state=None):
        self.job_id = job_id
        self.job_state = job_state
        self.job_tmp_directory = job_tmp_directory
        self.job_uuid = job_uuid
        self.job_certificate = job_certificate
        self.job_owner = job_owner
        self.job_node = job_node
        self.gui_state = gui_state

    def serialise(self):
        return {
            "job_id": self.job_id,
            "job_state": self.job_state,
            "job_tmp_directory": self.job_tmp_directory,
            "job_uuid": self.job_uuid,
            "job_owner": self.job_owner,
            "job_node": self.job_node,
            "gui_state": self.gui_state
        }
