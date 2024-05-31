import sys
import subprocess
import os

def print_usage():
    usage = """
    Usage:
        sudo python /opt/sysmon-utils/sysmon-cli.py addhost <host_name> --address <hostname_or_ip> [--template <template_name>]
        sudo python /opt/sysmon-utils/sysmon-cli.py removehost <host_name>
        sudo python /opt/sysmon-utils/sysmon-cli.py listhosts
        sudo python /opt/sysmon-utils/sysmon-cli.py addtemplate <host_name> --template <template_name>
        sudo python /opt/sysmon-utils/sysmon-cli.py addservice <host_name> --service <service_template>
        sudo python /opt/sysmon-utils/sysmon-cli.py listservices <host_name>
        sudo python /opt/sysmon-utils/sysmon-cli.py removeservice <host_name> --service <service_name>
    """
    print(usage)

def execute_command(command):
    try:
        env = os.environ.copy()
        # Preserve environment variables, especially PATH
        subprocess.run(command, check=True, shell=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}")
        sys.exit(1)

def restart_services():
    services = ["naemon", "thruk", "apache2"]
    for service in services:
        try:
            subprocess.run(f"sudo systemctl restart {service}", check=True, shell=True)
        except subprocess.CalledProcessError:
            if service == "thruk":
                try:
                    subprocess.run(f"sudo systemctl restart {service}", check=True, shell=True)
                except subprocess.CalledProcessError as e:
                    print(f"Failed to restart {service} service twice: {e}")
                    sys.exit(1)
            else:
                print(f"Failed to restart {service} service: {e}")
                sys.exit(1)

def add_host(host_name, address, template=None):
    command = f"sudo PYTHONPATH=$PYTHONPATH:/opt/okconfig okconfig addhost {host_name}"
    if template:
        command += f" --template {template}"
    command += f" --address {address} --force"
    execute_command(command)
    restart_services()

def remove_host(host_name):
    execute_command(f"sudo pynag delete where object_type=service and host_name={host_name}")
    execute_command(f"sudo pynag delete where object_type=host and host_name={host_name}")
    restart_services()

def list_hosts():
    execute_command("sudo pynag list host_name address WHERE object_type=host | egrep -v '^null'")

def add_template(host_name, template_name):
    execute_command(f"sudo PYTHONPATH=$PYTHONPATH:/opt/okconfig okconfig addtemplate {host_name} --template {template_name} --force")
    restart_services()

def add_service(host_name, service_template):
    execute_command(f'sudo pynag add service use="{service_template}" host_name={host_name} --filename=/etc/naemon/okconfig/hosts/default/{host_name}-instance.cfg')
    restart_services()

def list_services(host_name):
    execute_command(f"sudo pynag list host_name use WHERE object_type=service and host_name={host_name}")

def remove_service(host_name, service_name):
    execute_command(f"sudo pynag delete where object_type=service and host_name={host_name} and use={service_name}")
    restart_services()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == "addhost":
            if len(sys.argv) >= 5 and "--address" in sys.argv:
                host_name = sys.argv[2]
                address_index = sys.argv.index("--address")
                address = sys.argv[address_index + 1]
                template = None
                if "--template" in sys.argv:
                    template_index = sys.argv.index("--template")
                    template = sys.argv[template_index + 1]
                add_host(host_name, address, template)
            else:
                print_usage()
                sys.exit(1)
        elif command == "removehost" and len(sys.argv) == 3:
            remove_host(sys.argv[2])
        elif command == "listhosts" and len(sys.argv) == 2:
            list_hosts()
        elif command == "addtemplate" and len(sys.argv) == 5 and sys.argv[3] == "--template":
            add_template(sys.argv[2], sys.argv[4])
        elif command == "addservice" and len(sys.argv) == 5 and sys.argv[3] == "--service":
            add_service(sys.argv[2], sys.argv[4])
        elif command == "listservices" and len(sys.argv) == 3:
            list_services(sys.argv[2])
        elif command == "removeservice" and len(sys.argv) == 5 and sys.argv[3] == "--service":
            remove_service(sys.argv[2], sys.argv[4])
        else:
            print_usage()
            sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
