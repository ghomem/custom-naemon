import sys
import subprocess
import os
import re

def print_usage():
    usage = """
    \033[94mUsage:\033[0m
        sysmon-cli \033[92madd-host\033[0m <host_name> [--address <fqdn_or_ip>] [--template <template_name>]
        sysmon-cli \033[92mremove-host\033[0m <host_name>
        sysmon-cli \033[92mlist-hosts\033[0m
        sysmon-cli \033[92madd-template\033[0m <host_name> --template <template_name>
        sysmon-cli \033[92madd-service\033[0m <host_name> --service <service_template> [--description <description>]
        sysmon-cli \033[92mremove-service\033[0m <host_name> --service <service_name>
        sysmon-cli \033[92mmodify-service\033[0m <host_name> --service <service_name>
        sysmon-cli \033[92mlist-host-services\033[0m <host_name>
        sysmon-cli \033[92mlist-available-services\033[0m [--details]
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

def host_exists(host_name):
    try:
        result = subprocess.run(f"sudo pynag list host_name WHERE object_type=host and host_name={host_name}",
                                shell=True, check=True, capture_output=True, text=True)
        return host_name in result.stdout
    except subprocess.CalledProcessError:
        return False

def service_template_exists(service_template):
    try:
        result = subprocess.run("grep name /etc/naemon/conf.d/templates/services.cfg | awk '{ print $2 }' | sort",
                                shell=True, check=True, capture_output=True, text=True)
        return service_template in result.stdout.split()
    except subprocess.CalledProcessError:
        return False

def template_exists(template_name):
    template_path = f"/etc/naemon/okconfig/examples/{template_name}.cfg-example"
    return os.path.isfile(template_path)

def add_host(host_name, address, template=None):
    command = f"sudo PYTHONPATH=$PYTHONPATH:/opt/okconfig okconfig addhost {host_name}"
    if template:
        command += f" --template {template}"
    command += f" --address {address}"
    execute_command(command)
    restart_services()

def remove_host(host_name):
    execute_command(f"sudo pynag delete where object_type=service and host_name={host_name}")
    execute_command(f"sudo pynag delete where object_type=host and host_name={host_name}")
    execute_command(f"rm -f /etc/naemon/okconfig/hosts/default/{host_name}-host.cfg")
    execute_command(f"rm -f /etc/naemon/okconfig/hosts/default/{host_name}-instance.cfg")
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
    if not host_exists(host_name):
        print(f"\033[91mHost '{host_name}' does not exist.\033[0m")
        return
    if not template_exists(template_name):
        print(f"\033[91mTemplate '{template_name}' does not exist.\033[0m")
        return

    execute_command(f"sudo PYTHONPATH=$PYTHONPATH:/opt/okconfig okconfig addtemplate {host_name} --template {template_name} --force")
    restart_services()

def add_service(host_name, service_template, description=None):
    if not host_exists(host_name):
        print(f"\033[91mHost '{host_name}' does not exist.\033[0m")
        return

    if not service_template_exists(service_template):
        print(f"\033[91mService template '{service_template}' does not exist.\033[0m")
        return

    instance_file = f"/etc/naemon/okconfig/hosts/default/{host_name}-instance.cfg"

    # Check for existing services with the same use and description
    existing_services = check_existing_services(instance_file, service_template, description)

    if existing_services:
        if description:
            print(f"\033[91mA service with use '{service_template}' and description '{description}' already exists.\033[0m")
        else:
            print(f"\033[91mA service with use '{service_template}' and default description already exists.\033[0m")
        print("Please add the new service with a different --description to avoid conflicts.")
        return

    if description:
        service_command = f'sudo pynag add service use="{service_template}" host_name={host_name} service_description="{description}" --filename={instance_file}'
    else:
        service_command = f'sudo pynag add service use="{service_template}" host_name={host_name} --filename={instance_file}'

    execute_command(service_command)
    restart_services()

def check_existing_services(file_path, service_template, description=None):
    try:
        with open(file_path, "r") as f:
            content = f.read()

        service_blocks = content.split("define service {")
        for block in service_blocks[1:]:
            lines = block.strip().split('\n')
            use_match = any(line.strip().startswith(f"use") and service_template in line for line in lines)

            if use_match:
                if description:
                    # Check for exact description match
                    if any(line.strip().startswith("service_description") and description in line for line in lines):
                        return True
                else:
                    # Check if no explicit description is set
                    if not any(line.strip().startswith("service_description") for line in lines):
                        return True

        return False
    except FileNotFoundError:
        print(f"\033[91mInstance file not found: {file_path}\033[0m")
        return False

def list_services(host_name):
    execute_command(f"sudo pynag list host_name use WHERE object_type=service and host_name={host_name}")
    print(f"\033[92mThe host is defined in /etc/naemon/okconfig/hosts/default/{host_name}-host.cfg\033[0m")
    print(f"\033[92mThe host services are defined in /etc/naemon/okconfig/hosts/default/{host_name}-instance.cfg\033[0m")

def list_services_to_remove(host_name, service_name):
    command = f"sudo pynag list where object_type=service and host_name={host_name} and use={service_name}"
    process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if process.returncode != 0:
        print(f"\033[91mError: {process.stderr}\033[0m")
    output = process.stdout
    services = []
    for line in output.splitlines():
        if line.startswith("service"):
            parts = line.split()
            shortname = " ".join(parts[1:-1])
            services.append(shortname)
    return services

def remove_service(host_name, service_name):
    services = list_services_to_remove(host_name, service_name)
    if not services:
        print(f"\033[91mNo services found for host {host_name} with use {service_name}.\033[0m")
        return
    elif len(services) == 1:
        shortname = services[0]
        execute_command(f"sudo pynag delete where object_type=service and host_name={host_name} and use={service_name} and shortname='{shortname}'")
        print(f"\033[92mService '{shortname}' has been successfully removed.\033[0m")
    else:
        print(f"\033[93m{len(services)} services found for host {host_name} with use {service_name}:\033[0m")
        for idx, shortname in enumerate(services, start=1):
            print(f"\033[94m{idx}. {shortname}\033[0m")
        choice = input("\033[93mType the number of the service you wish to remove or 'all' to delete all services: \033[0m")
        if choice.lower() == 'all':
            for shortname in services:
                execute_command(f"sudo pynag delete where object_type=service and host_name={host_name} and use={service_name} and shortname='{shortname}'")
            print(f"\033[92mAll services have been successfully removed.\033[0m")
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(services):
                    shortname = services[idx]
                    execute_command(f"sudo pynag delete where object_type=service and host_name={host_name} and use={service_name} and shortname='{shortname}'")
                    print(f"\033[92mService '{shortname}' has been successfully removed.\033[0m")
                else:
                    print("\033[91mInvalid choice. No services were deleted.\033[0m")
            except ValueError:
                print("\033[91mInvalid input. No services were deleted.\033[0m")
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

    try:
        with open(instance_file, "r") as f:
            content = f.read()
    except FileNotFoundError as e:
        print(f"\033[91mInstance file not found: {e}\033[0m")
        return

    service_blocks = content.split("define service {")
    matching_blocks = []

    for i, block in enumerate(service_blocks[1:], start=1):
        lines = block.strip().split('\n')
        if any(re.match(rf'\s*use\s+{service_name}', line) for line in lines):
            service_description = next(
                (line.split('service_description', 1)[1].strip() for line in lines if line.strip().startswith('service_description')),
                "Service with default description"
            )
            matching_blocks.append((i, block, service_description))

    if not matching_blocks:
        print(f"\033[91mThe given service is not defined for the given host.\033[0m")
        return

    # Add numbered comments to matching blocks
    for i, (index, block, description) in enumerate(matching_blocks, start=1):
        service_blocks[index] = f"# Service {i}\n" + block

    # If multiple services are found, let the user choose one
    if len(matching_blocks) > 1:
        print(f"\033[93m{len(matching_blocks)} services found for host {host_name} with use {service_name}:\033[0m")
        for i, (_, _, description) in enumerate(matching_blocks, start=1):
            print(f"\033[94m{i}. {description}\033[0m")
        choice = input("\033[93mType the number of the service you wish to modify: \033[0m")
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(matching_blocks):
                selected_block_index = matching_blocks[idx][0]
            else:
                print("\033[91mInvalid choice. No service was modified.\033[0m")
                return
        except ValueError:
            print("\033[91mInvalid input. No service was modified.\033[0m")
            return
    else:
        selected_block_index = matching_blocks[0][0]

    # Get custom variables for the given service from the templates file
    service_vars = get_service_custom_vars(service_name)

    if not service_vars:
        print(f"\033[91mThe given service does not have custom variables.\033[0m")
        return

    print(f"\033[92mAvailable custom variables:\033[0m")
    variables_list = list(service_vars.keys()) + ['notifications_enabled'] + ['service_description']
    for i, var in enumerate(variables_list, start=1):
        print(f"\033[93m{i}. {var}\033[0m")

    # Interactive prompt
    modified_vars = {}
    print("\033[94mWhen you are done, please type Exit.\033[0m")
    while True:
        var_input = input("Enter the number of the custom variable to modify: ").strip()
        if var_input.lower() == "exit":
            break
        try:
            var_index = int(var_input) - 1
            if 0 <= var_index < len(variables_list):
                var = variables_list[var_index]
            else:
                print("\033[91mInvalid choice. Please select a number from the list.\033[0m")
                continue
        except ValueError:
            print("\033[91mInvalid input. Please enter a number.\033[0m")
            continue
        value = input(f"Enter the value for {var}: ").strip()
        if var.endswith("_THRESHOLD") or var.endswith("_PORT") or var == "__TCP_PORT" or "WARNING" in var or "CRITICAL" in var:
            if not value.isdigit():
                print("\033[91mThe value must be an integer.\033[0m")
                continue
        if var == "notifications_enabled":
            if not value.isdigit() or int(value) not in [0, 1]:
                print("\033[91mThis variable takes only a boolean value [0 for notificattions off or 1 for notifications on].\033[0m")
                continue
        modified_vars[var] = value

    # Update the selected service block with modified variables
    lines = service_blocks[selected_block_index].strip().split("\n")
    for var, value in modified_vars.items():
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith(var):
                lines[i] = f"        {var} {value}"
                found = True
                break
        if not found:
            lines.insert(-1, f"        {var} {value}")  # Insert before the last line

    service_blocks[selected_block_index] = "\n".join(lines) + "\n"

    # Write the updated content back to the file
    try:
        with open(instance_file, "w") as f:
            f.write("define service {".join(service_blocks))
        print("\033[92mService modified successfully.\033[0m")
    except Exception as e:
        print(f"\033[91mFailed to update instance file: {e}\033[0m")
        return

    # Remove the added comments
    remove_comments(instance_file)
    restart_services()

def remove_comments(file_path):
    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Remove the added comments
        content = re.sub(r'# Service \d+\n', '', content)

        with open(file_path, "w") as f:
            f.write(content)
    except Exception as e:
        print(f"\033[91mFailed to remove comments: {e}\033[0m")

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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == "add-host":
            if len(sys.argv) not in [3, 5, 7]:
                print_usage()
                sys.exit(1)
            host_name = sys.argv[2]
            address = host_name
            template = None
            if len(sys.argv) >= 5:
                if "--address" not in sys.argv and "--template" not in sys.argv:
                    print_usage()
                    sys.exit(1)
                if len (sys.argv) == 7 and ("--address" not in sys.argv or "--template" not in sys.argv):
                    print_usage()
                    sys.exit(1)
                if "--address" in sys.argv:
                    address_index = sys.argv.index("--address")
                    address = sys.argv[address_index + 1]
                if "--template" in sys.argv:
                    template_index = sys.argv.index("--template")
                    template = sys.argv[template_index + 1]
            add_host(host_name, address, template)
        elif command == "remove-host" and len(sys.argv) == 3:
            remove_host(sys.argv[2])
        elif command == "list-hosts" and len(sys.argv) == 2:
            list_hosts()
        elif command == "add-template" and len(sys.argv) == 5 and sys.argv[3] == "--template":
            add_template(sys.argv[2], sys.argv[4])
        elif command == "add-service":
            if len(sys.argv) not in [5, 7]:
                print_usage()
                sys.exit(1)
            if sys.argv[3] != "--service":
                print_usage()
                sys.exit(1)
            host_name = sys.argv[2]
            service_template = sys.argv[4]
            description = None
            if len(sys.argv) == 7:
                if "--description" not in sys.argv:
                    print_usage()
                    sys.exit(1)
                description_index = sys.argv.index("--description")
                description = sys.argv[description_index + 1]
            add_service(host_name, service_template, description)
        elif command == "list-host-services" and len(sys.argv) == 3:
            list_services(sys.argv[2])
        elif command == "remove-service" and len(sys.argv) == 5 and sys.argv[3] == "--service":
            remove_service(sys.argv[2], sys.argv[4])
        elif command == "modify-service" and len(sys.argv) == 5 and sys.argv[3] == "--service":
            modify_service(sys.argv[2], sys.argv[4])
        elif command == "list-available-services" and (len(sys.argv) == 2 or (len(sys.argv) == 3 and sys.argv[2] == "--details")):
            details = "--details" in sys.argv
            all_services(details)
        else:
            print_usage()
            sys.exit(1)
    except Exception as e:
        print(f"\033[91mAn error occurred: {e}\033[0m")
        sys.exit(1)
