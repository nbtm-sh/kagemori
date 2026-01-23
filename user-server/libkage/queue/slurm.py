import subprocess, socket, logging, datetime

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
        logging.getLogger().debug(f"Execute `{format_command}`")
        output = subprocess.check_output(command).decode("utf-8").replace(" ", "").split()
        format_output = " ".join(output)
        logging.getLogger().debug(f"Got '{output}'")
        return output 

    @staticmethod
    def _slurm_scancel(job_id):
        command = [SlurmManager.COMMNAD_SCANCEL, job_id]
        format_command = ' '.join(command)
        logging.getLogger().debug(f"Execute `{format_command}`")
        output = subprocess.check_output(command)
        logging.getLogger().debug(f"Got '{output}'")
        return output

    @staticmethod
    def _slurm_sbatch(script, output_file, comment, **kwargs):
        export = "ALL"
        if len(kwargs) > 0:
            for k, v in kwargs.items():
                export += f",{k}={v}"
        comment = f"\"{comment}\""
        command = [SlurmManager.COMMAND_SBATCH, "--export", export, "--output", output_file, "--comment", f"{comment}", script]
        format_command = ' '.join(command)
        logging.getLogger().debug(f"Execute `{format_command}`")
        job_id = subprocess.check_output(command).decode("utf-8").split()[-1]
        logging.getLogger().debug(f"Got '{job_id}'")
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
        # Low priority as DNS should be used regardless of IPv6 or IPv4
        hostname = hostname.split(':')[0]
        return socket.gethostbyname(hostname)
    
    @staticmethod
    def submit_job(script, output_file="slurm-%j.out", comment="kagemori", **kwargs):
        return SlurmManager._slurm_sbatch(script, output_file, comment, **kwargs)

    @staticmethod
    def cancel_job(job_id):
        return SlurmManager._slurm_scancel(job_id)

    @staticmethod
    def end_time(job_id):
        elapsed_time = SlurmManager._slurm_sacct("Elapsed", job_id)
        time_limit = SlurmManager._slurm_sacct("TimeLimit", job_id)

        if len(elapsed_time) == 0 or len(time_limit) == 0:
            return

        elapsed_time = elapsed_time[0]
        time_limit = time_limit[0]

        elapsed_date = datetime.datetime.strptime(elapsed_time, "%H:%M:%S")
        time_limit_date = datetime.datetime.strptime(time_limit, "%H:%M:%S")

        elapsed_delta = datetime.timedelta(hours=elapsed_date.hour, minutes=elapsed_date.minute, seconds=elapsed_date.second)
        time_limit_delta = datetime.timedelta(hours=time_limit_date.hour, minutes=time_limit_date.minute, seconds=time_limit_date.second)

        now = datetime.datetime.utcnow()
        now -= elapsed_delta
        now += time_limit_delta
        
        return now

