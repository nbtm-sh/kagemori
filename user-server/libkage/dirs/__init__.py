import os, pathlib, shutil

class DirWrapper:
    def __init__(self, username, uid, prefix="~/.config/kagemori", temp_dir=".tmp", job_dir_prefix = "job-"):
        self.username = username 
        self.uid = str(uid)
        self.prefix = prefix
        self.temp_dir = temp_dir
        self.job_dir_prefix = job_dir_prefix
        #self.nginx_prefix = prefix

    def _get_temp_dir(self, job_uuid):
        job_id = str(job_uuid)
        job_tempdir_path = os.path.join(
            self.format_path(self.prefix),
            self.format_path(self.temp_dir),
            self.format_path(f"{self.job_dir_prefix}{job_id}/")
        )
        return job_tempdir_path
    
    def format_path(self, path):
        path = path.replace("%h", str(pathlib.Path.home()))
        path = path.replace("%u", self.username)
        path = path.replace("%i", self.uid)
        path = os.path.expanduser(path)

        return path


    def create_temporary_job_dir(self, job_uuid):
        job_tempdir_path = self._get_temp_dir(job_uuid)
        os.makedirs(job_tempdir_path)

        return job_tempdir_path

    def get_temporary_job_dir(self, job_uuid):
        return self._get_temp_dir(job_uuid)

    def clean_up_job_dir(self, job_uuid):
        job_tempdir_path = self._get_temp_dir(job_uuid)
        shutil.rmtree(job_tempdir_path)

    def create_dir_in_temp_dir(self, job_uuid, dir_name, dry=False):
        if not os.path.exists(self._get_temp_dir(job_uuid)):
            # Create the temporary path if not exists 
            self.create_temporary_job_dir(job_uuid)

        base_path = self._get_temp_dir(job_uuid)
        full_path = os.path.join(base_path, dir_name)
        if not dry:
            if not os.path.exists(full_path):
                os.makedirs(full_path)

        return full_path
    
    def get_dir_in_temp_dir(self, job_uuid, dir_name):
        base_path = self._get_temp_dir(job_uuid)
        return os.path.join(base_path, dir_name)
    
    def create_directory_in_prefix(self, path):
        path = self.format_path(path)
        tmp_prefix = self.format_path(self.prefix)
        new_dir = os.path.join(tmp_prefix, path)

        os.makedirs(new_dir)
