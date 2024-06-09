import sys
import subprocess
import os
import re

def print_usage():
    usage = """
    \033[94mUsage:\033[0m
        sudo python /opt/sysmon-utils/sysmon-cli.py \033[92madd-host\033[0m <host_name> --address <hostname_or_ip> [--template <template_name>]
        sudo python /opt/sysmon-utils/sysmon-cli.py \033[92mremove-host\033[0m <host_name>
        sudo python /opt/sysmon-utils/sysmon-cli.py \033[92mlist-hosts\033[0m
        sudo python /opt/sysmon-utils/sysmon-cli.py \033[92madd-template\033[0m <host_name> --template <template_name>
        sudo python /opt/sysmon-utils/sysmon-cli.py \033[92madd-service\033[0m <host_name> --service <service_template>
        sudo python /opt/sysmon-utils/sysmon-cli.py \033[92mlist-host-services\033[0m <host_name>
        sudo python /opt/sysmon-utils/sysmon-cli.py \033[92mremove-service\033[0m <host_name> --service <service_name>
        sudo python /opt/sysmon-utils/sysmon-cli.py \033[92mmodify-service\033[0m <host_name> --service <service_name>
        sudo python /opt/sysmon-utils/sysmon-cli.py \033[92mlist-available-services\033[0m [--details]
    """
    print(usage)

def execute_command(command):
    try:
        env = os.environ.copy()
        # Preserve environment variables, especially PATH
        subprocess.run(command, check=True, shell=True, env=env)
    except subprocess.CalledProcessError as e:
        print(f"\033[91mCommand failed: {e}\033[0m")
        sys.exit(1)

def restart_services():
    services = ["naemon", "thruk", "apache2"]
    for service in services:
        try:
            subprocess.run(f"sudo systemctl restart {service}", check=True, shell=True)
        except subprocess.CalledProcessError as ge:
            if service == "thruk":
                try:
                    subprocess.run(f"sudo systemctl restart {service}", check=True, shell=True)
                except subprocess.CalledProcessError as e:
                    print(f"\033[91mFailed to restart {service} service twice: {e}\033[0m")
                    sys.exit(1)
            else:
                print(f"\033[91mFailed to restart {service} service: {ge}\033[0m")
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
    try:
        result = subprocess.run("sudo pynag list host_name address WHERE object_type=host | egrep -v '^null'", 
                                shell=True, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"\033[91mCommand failed: {e}\033[0m")
        sys.exit(1)

    lines = result.stdout.strip().split('\n')
    # Print the header
    print(f"\033[94m{'host_name':<20} {'address':<20} {'host_definition_file':<60} {'service_definition_file':<60}\033[0m")
    print('\033[90m' + '-' * 140 + '\033[0m')
    
    for line in lines:
        if "---" in line or "host_name" in line:
            continue
        if line.strip():
            parts = line.split()
            host_name = parts[0]
            address = parts[1]
            host_def_file = f"/etc/naemon/okconfig/hosts/default/{host_name}-host.cfg"
            service_def_file = f"/etc/naemon/okconfig/hosts/default/{host_name}-instance.cfg"
            print(f"\033[92m{host_name:<20} {address:<20} {host_def_file:<60} {service_def_file:<60}\033[0m")
    
    print('\033[90m' + '-' * 140 + '\033[0m')

def add_template(host_name, template_name):
    execute_command(f"sudo PYTHONPATH=$PYTHONPATH:/opt/okconfig okconfig addtemplate {host_name} --template {template_name} --force")
    restart_services()

def add_service(host_name, service_template):
    execute_command(f'sudo pynag add service use="{service_template}" host_name={host_name} --filename=/etc/naemon/okconfig/hosts/default/{host_name}-instance.cfg')
    restart_services()

def list_services(host_name):
    execute_command(f"sudo pynag list host_name use WHERE object_type=service and host_name={host_name}")
    print(f"\033[92mThe host is defined in /etc/naemon/okconfig/hosts/default/{host_name}-host.cfg\033[0m")
    print(f"\033[92mThe host services are defined in /etc/naemon/okconfig/hosts/default/{host_name}-instance.cfg\033[0m")

def remove_service(host_name, service_name):
    execute_command(f"sudo pynag delete where object_type=service and host_name={host_name} and use={service_name}")
    restart_services()

def all_services(details=False):
    try:
        with open("/etc/naemon/conf.d/templates/services.cfg", "r") as f:
            content = f.read()
    except FileNotFoundError as e:
        print(f"\033[91mFile not found: {e}\033[0m")
        sys.exit(1)

    service_blocks = content.split("define service {")
    services = {}

    for block in service_blocks[1:]:
        lines = block.strip().split("\n")
        name = None
        custom_vars = {}
        for line in lines:
            if "name" in line:
                name = line.split()[1]
            if line.strip().startswith("__"):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    var, value = parts
                    custom_vars[var.strip()] = value.strip()
        if name:
            services[name] = custom_vars

    for name in sorted(services.keys()):
        print(f"\n\033[94m{name}\033[0m\n\033[90m{'-' * len(name)}\033[0m")
        if details:
            if services[name]:
                for var, value in services[name].items():
                    print(f"  \033[93m{var:<25}\033[0m : \033[92m{value}\033[0m")
            else:
                print("  \033[91mNo custom variables defined.\033[0m")

def get_service_custom_vars(service_name):
    try:
        with open("/etc/naemon/conf.d/templates/services.cfg", "r") as f:
            content = f.read()
    except FileNotFoundError as e:
        print(f"\033[91mFile not found: {e}\033[0m")
        sys.exit(1)

    service_blocks = content.split("define service {")
    for block in service_blocks[1:]:
        lines = block.strip().split("\n")
        for line in lines:
            if re.match(rf'\s*name\s+{service_name}', line):
                custom_vars = {}
                for line in lines:
                    if line.strip().startswith("__"):
                        parts = line.split(None, 1)
                        if len(parts) == 2:
                            var, value = parts
                            custom_vars[var.strip()] = value.strip()
                return custom_vars
    return {}

def service_exists_in_host(instance_file, service_name):
    try:
        with open(instance_file, "r") as f:
            content = f.read()
    except FileNotFoundError as e:
        print(f"\033[91mInstance file not found: {e}\033[0m")
        return False

    service_blocks = content.split("define service {")
    for block in service_blocks[1:]:
        lines = block.strip().split("\n")
        for line in lines:
            if re.match(rf'\s*use\s+{service_name}', line):
                return True
    return False

def modify_service(host_name, service_name):
    instance_file = f"/etc/naemon/okconfig/hosts/default/{host_name}-instance.cfg"

    # Check if the service exists for the given host
    if not service_exists_in_host(instance_file, service_name):
        print(f"\033[91mThe given service is not defined for the given host.\033[0m")
        return

    # Get custom variables for the given service from the templates file
    service_vars = get_service_custom_vars(service_name)

    if not service_vars:
        print(f"\033[91mThe given service does not have custom variables.\033[0m")
        return

    print(f"\033[92mAvailable custom variables:\033[0m")
    for var in service_vars:
        print(f"\033[93m{var}\033[0m")

    # Interactive prompt
    modified_vars = {}
    print("\033[94mWhen you are done, please type Exit.\033[0m")
    while True:
        var = input("Enter the custom variable to modify: ").strip()
        if var.lower() == "exit":
            break
        if var not in service_vars:
            print("\033[91mThe custom variable does not exist.\033[0m")
            continue
        value = input(f"Enter the value for {var}: ").strip()
        if var.endswith("_THRESHOLD") or var.endswith("_PORT") or var == "__TCP_PORT":
            if not value.isdigit():
                print("\033[91mThe value must be an integer.\033[0m")
                continue
        modified_vars[var] = value

    # Update the instance file with modified variables
    try:
        with open(instance_file, "r") as f:
            content = f.read()
    except FileNotFoundError as e:
        print(f"\033[91mInstance file not found: {e}\033[0m")
        return

    service_blocks = content.split("define service {")
    updated_content = [service_blocks[0]]  # Start with the initial content before the first service block

    for block in service_blocks[1:]:
        lines = block.strip().split("\n")
        if any(re.match(rf'\s*use\s+{service_name}', line) for line in lines):
            for var, value in modified_vars.items():
                found = False
                for i, line in enumerate(lines):
                    if line.strip().startswith(var):
                        lines[i] = f"        {var} {value}"
                        found = True
                        break
                if not found:
                    lines.insert(-1, f"        {var} {value}")  # Insert before the last line
            updated_content.append("define service {\n" + "\n".join(lines) + "\n")
        else:
            lines = [line if not re.match(r'\s*use\s+', line) else f"        {line.strip()}" for line in lines]
            updated_content.append("define service {\n" + "\n".join(lines) + "\n")

    try:
        with open(instance_file, "w") as f:
            f.write("\n".join(updated_content))
        print("\033[92mService modified successfully.\033[0m")
    except Exception as e:
        print(f"\033[91mFailed to update instance file: {e}\033[0m")
        sys.exit(1)
    restart_services()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == "add-host":
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
        elif command == "remove-host" and len(sys.argv) == 3:
            remove_host(sys.argv[2])
        elif command == "list-hosts" and len(sys.argv) == 2:
            list_hosts()
        elif command == "add-template" and len(sys.argv) == 5 and sys.argv[3] == "--template":
            add_template(sys.argv[2], sys.argv[4])
        elif command == "add-service" and len(sys.argv) == 5 and sys.argv[3] == "--service":
            add_service(sys.argv[2], sys.argv[4])
        elif command == "list-host-services" and len(sys.argv) == 3:
            list_services(sys.argv[2])
        elif command == "remove-service" and len(sys.argv) == 5 and sys.argv[3] == "--service":
            remove_service(sys.argv[2], sys.argv[4])
        elif command == "modify-service" and len(sys.argv) == 5 and sys.argv[3] == "--service":
            modify_service(sys.argv[2], sys.argv[4])
        elif command == "list-available-services" and len(sys.argv) in [2, 3] and (len(sys.argv) == 2 or sys.argv[2] == "--details"):
            details = "--details" in sys.argv
            all_services(details)
        else:
            print_usage()
            sys.exit(1)
    except Exception as e:
        print(f"\033[91mAn error occurred: {e}\033[0m")
        sys.exit(1)

