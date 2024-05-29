#!/bin/bash

set -e

# Function to handle errors gracefully
handle_error() {
    echo "Error on line $1"
    exit 1
}
trap 'handle_error $LINENO' ERR

export DEBIAN_FRONTEND=noninteractive

# Download and add Naemon's GPG key
echo "Adding Naemon's GPG key..."
curl -s -o /etc/apt/trusted.gpg.d/naemon.asc "https://build.opensuse.org/projects/home:naemon/signing_keys/download?kind=gpg"

# Add Naemon's repository
echo "Adding Naemon's repository..."
echo "deb [signed-by=/etc/apt/trusted.gpg.d/naemon.asc] http://download.opensuse.org/repositories/home:/naemon/xUbuntu_$(lsb_release -rs)/ ./" > /etc/apt/sources.list.d/naemon-stable.list
apt-get update -q

# Install Naemon
echo "Installing Naemon..."
apt-get install naemon -y -q -o Dpkg::Options::="--force-confold" -o Dpkg::Options::="--force-confdef"

# Setup Naemon user's SSH directory
echo "Setting up Naemon user's SSH directory..."
mkdir -p /home/naemon/.ssh
chown -R naemon:naemon /home/naemon/
chmod 750 /home/naemon
chmod 700 /home/naemon/.ssh

# Stop Naemon service
echo "Stopping Naemon service..."
systemctl stop naemon

# Run Puppet agent
echo "Running Puppet agent..."
puppet agent -t || true

# Add Naemon user to necessary groups
echo "Adding Naemon user to www-data and sudo groups..."
usermod -aG www-data naemon
usermod -aG sudo naemon

# Adjust permissions for Naemon cache directory
echo "Adjusting permissions for Naemon cache directory..."
chmod g+w /var/cache/naemon/

# Clone and setup okconfig
echo "Cloning and setting up okconfig..."
cd /opt
git clone https://github.com/opinkerfi/okconfig.git
echo 'export PYTHONPATH=$PYTHONPATH:/opt/okconfig' > /etc/profile.d/okconfig.sh
cp /opt/okconfig/etc/okconfig.conf /etc/okconfig.conf
source /etc/profile
ln -s /opt/okconfig/usr/share/okconfig /usr/share/
ln -s /opt/okconfig/usr/bin/okconfig /usr/local/bin/
mkdir -p /etc/naemon/okconfig/examples/

# Install necessary Python packages
echo "Installing necessary Python packages..."
apt-get install python3 python3-venv python3-pip -y -q
pip3 install pynag
ln -s /usr/bin/python3 /usr/bin/python

# Update okconfig configuration
echo "Updating okconfig configuration..."
sed -i 's|^nagios_config.*|nagios_config           /etc/naemon/naemon.cfg|' /etc/okconfig.conf
sed -i 's|^destination_directory.*|destination_directory           /etc/naemon/okconfig/|' /etc/okconfig.conf
sed -i 's|^examples_directory_local.*|examples_directory_local           /etc/naemon/okconfig/examples|' /etc/okconfig.conf

# Comment out specific line in okconfig
echo "Commenting out specific line in okconfig..."
sed -i 's|^    linefh.write(template)|#    linefh.write(template)|' /opt/okconfig/usr/bin/okconfig

# Clone custom-naemon repository and set up configurations
echo "Cloning custom-naemon repository and setting up configurations..."
cd /tmp
git clone https://github.com/ghomem/custom-naemon.git
chmod -R 664 /tmp/custom-naemon/
chown -R naemon:naemon /tmp/custom-naemon/src/naemon/

# Copy custom configurations to Naemon directory
echo "Copying custom configurations to Naemon directory..."
cp /tmp/custom-naemon/src/naemon/commands.cfg /etc/naemon/conf.d/
cp /tmp/custom-naemon/src/naemon/timeperiods.cfg /etc/naemon/conf.d/
cp /tmp/custom-naemon/src/naemon/24x7-nobackups.cfg /etc/naemon/conf.d/
cp /tmp/custom-naemon/src/naemon/services.cfg /etc/naemon/conf.d/templates/
cp /tmp/custom-naemon/src/naemon/templates.cfg /etc/naemon/conf.d/templates/

cp /tmp/custom-naemon/src/thruk/* /etc/thruk
cp /tmp/custom-naemon/src/okconfig/instance.cfg-example /etc/naemon/okconfig/examples/

# Initialize and verify okconfig
echo "Initializing and verifying okconfig..."
okconfig init
okconfig verify

# Remove unnecessary default configuration files
echo "Removing unnecessary default configuration files..."
cd /etc/naemon/conf.d
rm -f printer.cfg switch.cfg windows.cfg
rm -f templates/hosts.cfg templates/contacts.cfg

echo "Script completed successfully."
