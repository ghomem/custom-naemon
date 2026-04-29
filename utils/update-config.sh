#!/bin/bash

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root."
    exit 1
fi

cd /opt/custom-naemon

validate_naemon_config() {
    if sudo -u naemon naemon -v /etc/naemon/naemon.cfg > /tmp/sysmon-naemon-validate.out 2>&1; then
        echo "Naemon config validation passed."
    else
        echo "Naemon config validation failed. Services were not restarted."
        cat /tmp/sysmon-naemon-validate.out
        exit 1
    fi
}

restart_services() {
    validate_naemon_config

    echo "Restarting services..."
    systemctl restart naemon
    systemctl restart apache2
    systemctl restart thruk
}

# Ensure external/company-specific config directories exist.
# These directories are intentionally not populated or managed by custom-naemon.
mkdir -p /etc/naemon/external.d/commands.d
mkdir -p /etc/naemon/external.d/services.d
mkdir -p /etc/naemon/external.d/contacts.d
mkdir -p /etc/naemon/external.d/timeperiods.d
chown -R root:root /etc/naemon/external.d
chmod -R 755 /etc/naemon/external.d

# Pull the latest changes in the repository
echo "Pulling the latest changes..."
git pull

# Copying custom configurations to Naemon directory
echo "Copying custom configurations to Naemon directory..."
cp /opt/custom-naemon/src/naemon/commands.cfg /etc/naemon/conf.d/
cp /opt/custom-naemon/src/naemon/timeperiods.cfg /etc/naemon/conf.d/
cp /opt/custom-naemon/src/naemon/24x7-nobackups.cfg /etc/naemon/conf.d/
cp /opt/custom-naemon/src/naemon/services.cfg /etc/naemon/conf.d/templates/
cp /opt/custom-naemon/src/naemon/templates.cfg /etc/naemon/conf.d/templates/
cp /opt/custom-naemon/src/naemon/naemon.cfg /etc/naemon/

cp /opt/custom-naemon/src/thruk/* /etc/thruk
cp /opt/custom-naemon/src/okconfig/instance.cfg-example /etc/naemon/okconfig/examples/

cp /opt/custom-naemon/utils/sysmon-cli.py /opt/sysmon-utils/

restart_services
