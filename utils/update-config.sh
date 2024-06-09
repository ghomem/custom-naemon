#!/bin/bash

cd /opt/custom-naemon

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

cp /opt/custom-naemon/src/thruk/* /etc/thruk
cp /opt/custom-naemon/src/okconfig/instance.cfg-example /etc/naemon/okconfig/examples/

cp /opt/custom-naemon/utils/sysmon-cli.py /opt/sysmon-utils/
