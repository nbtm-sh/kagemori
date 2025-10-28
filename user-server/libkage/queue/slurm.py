import subprocess, socket, logging

class SlurmManager:
    COMMAND_SBATCH = "sbatch"
    COMMAND_SQUEUE = "squeue"
    COMMAND_SACCT = "sacct"
    COMMNAD_SCANCEL = "scancel"
    COMMAND_SBATCH = "sbatch"
    def __init__(self):
        pass
    
    @staticmethod
    def _slurm_sacct(output_format, job_id):
        command = [SlurmManager.COMMAND_SACCT, "-o", output_format, "-n", "-j", job_id]
        format_command = ' '.join(command)
        logging.getLogger().debug(f"Execute {format_command}")
        output = subprocess.check_output(command).decode("utf-8").replace(" ", "").split()
        logging.getLogger().debug(f"Got {output}")
        return output 

    @staticmethod
    def _slurm_scancel(job_id):
        command = [SlurmManager.COMMNAD_SCANCEL, job_id]
        format_command = ' '.join(command)
        logging.getLogger().debug(f"Execute {format_command}")
        output = subprocess.check_output(command)
        logging.getLogger().debug(f"Got {output}")
        return output

    @staticmethod
    def _slurm_sbatch(script, **kwargs):
        export = "ALL"
        if len(kwargs) > 0:
            for k, v in kwargs.items():
                export += f",{k}={v}"
        command = [SlurmManager.COMMAND_SBATCH, "--export", export, script]
        format_command = ' '.join(command)
        logging.getLogger().debug(f"Execute {format_command}")
        job_id = subprocess.check_output(command).decode("utf-8").split()[-1]
        logging.getLogger().debug(f"Got {job_id}")
        return job_id

    @staticmethod
    def get_job_state(job_id):
        state = SlurmManager._slurm_sacct("State", job_id)
        if len(state) > 0:
            return state[0]

    @staticmethod
    def get_job_node(job_id):
        node = SlurmManager._slurm_sacct("NodeList", job_id)
        if len(node) > 0:
            return node[0]

    @staticmethod
    def get_job_owner(job_id):
        owner = SlurmManager._slurm_sacct("User", job_id)
        if len(owner) > 0:
            return owner[0]
    
    @staticmethod
    def get_ip_literal(hostname):
        # TODO: IPv6 literals will be broken here
        hostname = hostname.split(':')[0]
        return socket.gethostbyname(hostname)
    
    @staticmethod
    def submit_job(script, **kwargs):
        return SlurmManager._slurm_sbatch(script, **kwargs)

    @staticmethod
    def cancel_job(job_id):
        return SlurmManager._slurm_scancel(job_id)

