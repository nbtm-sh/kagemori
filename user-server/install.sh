#!/bin/bash

set -xou pipefail

INSTALL_PATH="/opt/kagemori"

GIT_REPO="https://github.com/nbtm-sh/kagemori.git"
GIT_TAG="0.3rc2"
GIT_BRANCH="master"
CONFIG_PATH="/apps/opt/kagemori/config.yaml"

# Do not modify
_KAGEMORI_USER_SERVER_PATH="user-server"
_KAGEMORI_CONFIG_PATH="${HOME}/.config/kagemori/"
_KAGEMORI_REQUIREMENTS_FILE="requirements.txt"
_KAGEMORI_SERVER_FILE="server.py"
_KAGEMORI_SYSTEMD_MODULE_FILE="/etc/systemd/user/kagemori.service"
_KAGEMORI_START_SH_SCRIPT_FILE="start.sh"
_KAGEMORI_PYTHON_COMMAND="python3"
_KAGEMORI_PIP3_COMMAND="pip3"

# Create installation directory
mkdir -p ${INSTALL_PATH}

# Clone the git repo and checkout the tag
git clone ${GIT_REPO} ${INSTALL_PATH}/kagemori
cd ${INSTALL_PATH}/kagemori
git checkout tags/${GIT_TAG}

# Create and activate python virtual environment
cd ${INSTALL_PATH}/kagemori/${_KAGEMORI_USER_SERVER_PATH}
$_KAGEMORI_PYTHON_COMMAND -m venv venv
source ./venv/bin/activate

# Install required packages
$_KAGEMORI_PIP3_COMMAND install -r ${_KAGEMORI_REQUIREMENTS_FILE}

# Write start.sh script
cat > ${_KAGEMORI_START_SH_SCRIPT_FILE} << EOF
#!/bin/bash
source ${INSTALL_PATH}/kagemori/${_KAGEMORI_USER_SERVER_PATH}/venv/bin/activate
${_KAGEMORI_PYTHON_COMMAND} ${INSTALL_PATH}/kagemori/${_KAGEMORI_USER_SERVER_PATH}/${_KAGEMORI_SERVER_FILE}
EOF
chmod 755 ${_KAGEMORI_START_SH_SCRIPT_FILE}

# Write systemd module
_current_working_directory=$(pwd)
_systemd_dir=$(dirname "${_KAGEMORI_SYSTEMD_MODULE_FILE}")
## Create systemd directory if not exist
mkdir -p $_systemd_dir

## Write module file
cat > ${_KAGEMORI_SYSTEMD_MODULE_FILE} << EOF
[Unit]
Description=kagemori userland-service
After=network.target

[Service]
Type=simple
WorkingDirectory=%h
ExecStart=${_current_working_directory}/${_KAGEMORI_START_SH_SCRIPT_FILE}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

# Copy default configuration file
mkdir -p ${_KAGEMORI_CONFIG_PATH}
cp ${CONFIG_PATH} ${_KAGEMORI_CONFIG_PATH}

# Reload systemd
systemctl --user daemon-reload
