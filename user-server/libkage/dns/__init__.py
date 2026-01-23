import logging


def get_dns_servers(resolv_conf_path="/etc/resolv.conf"):
    servers = []
    logging.getLogger().debug(f"Finding DNS servers. Reading from {resolv_conf_path}")
    etc_resolv_lines = ""

    with open(resolv_conf_path, "r") as dns_fp:
        etc_resolv_lines = dns_fp.readlines()
        
    for i in etc_resolv_lines:
        if i.startswith("nameserver"):
            ip_address = i.split(" ")[1].strip()
            logging.getLogger().debug(f"Finding DNS servers: Found IP {ip_address}")
            servers.append(ip_address)

    if len(servers) == 0:
        logging.getLogger().warn(f"Finding DNS servers: No DNS servers were found")
    else:
        logging.getLogger().debug(f"Finding DNS servers: Found {len(servers)} server(s)")

    return servers
