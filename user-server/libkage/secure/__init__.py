import os, subprocess
import libkage.dirs

class SSLCertPath:
    # Object for containing the cert paths returned by SSL.create_certificate()
    def __init__(self, cert_out_path, cert_key_path):
        self.cert_out_path = cert_out_path
        self.cert_key_path = cert_key_path

class SSL:
    def __init__(self,
        dir_wrapper : libkage.dirs.DirWrapper,
        cert_expire_days = 1,
        cert_key_length = 4096,
        cert_country = "AU",
        cert_state = "New South Wales",
        cert_city = "Sydney",
        cert_company = "University of New South Wales",
        cert_company_section = "user",
        cert_common_name = "localhost",
        cert_dir = "cert",
        cert_key_out = "key.pem",
        cert_file_out = "cert.pem"):

        self.dir_wrapper = dir_wrapper
        self.cert_expire_days = cert_expire_days
        self.cert_key_length = cert_key_length
        self.cert_country = cert_country
        self.cert_state = cert_state
        self.cert_city = cert_city
        self.cert_company = cert_company
        self.cert_company_section = cert_company_section
        self.cert_common_name = cert_common_name
        self.cert_dir = cert_dir
        self.cert_key_out = cert_key_out
        self.cert_file_out = cert_file_out


    @staticmethod
    def _create_self_signed_cert(private_key_out : str, cert_out : str, expire_days = 1, key_length = 4096, cert_country= "AU", cert_state = "New South Wales", cert_city = "Sydney", cert_company = "University of New South Wales", cert_company_section = "user", cert_common_name = "localhost"):
        # Validate inputs
        key_length = str(int(key_length))
        expire_days = str(int(expire_days))

        # Construct command
        
        command = [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            f"rsa:{key_length}",
            "-keyout",
            private_key_out,
            "-out",
            cert_out,
            "-sha256",
            "-days",
            expire_days,
            "-nodes",
            "-subj",
            f"/C={cert_country}/ST={cert_state}/L={cert_city}/O={cert_company}/OU={cert_company_section}/CN={cert_common_name}"
        ]

        # Run command
        return subprocess.check_output(
                command
        )

    def create_certificate(self, job_uuid, common_name = "localhost"):
        cert_base_dir = self.dir_wrapper.create_dir_in_temp_dir(job_uuid, self.cert_dir)
        cert_out_path = os.path.join(cert_base_dir, self.cert_file_out)
        cert_key_path = os.path.join(cert_base_dir, self.cert_key_out)
        
        SSL._create_self_signed_cert(
            cert_key_path,
            cert_out_path,
            expire_days = self.cert_expire_days,
            key_length = self.cert_key_length,
            cert_country = self.cert_country,
            cert_state = self.cert_state,
            cert_city = self.cert_city,
            cert_company = self.cert_company,
            cert_company_section = self.cert_company_section,
            cert_common_name = common_name
        )

        return SSLCertPath(
            cert_out_path,
            cert_key_path
        )
