import os
import time
import shutil
import json
import subprocess
import urllib.request
import ssl
import webbrowser
import sys

try:
    import certifi
except ImportError:
    certifi = None


VERSION = "0.4"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".mylt")
os.makedirs(CONFIG_DIR, exist_ok=True)
HOSTS_FILE = os.path.join(CONFIG_DIR, "hosts.json")
SNIPPET_FILE = os.path.join(CONFIG_DIR, "snippet.json")
GREEN = "\033[92m"
MAGENTA = "\033[35m"
RED = "\033[31m"
RESET = "\033[0m"

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def message(text, seconds=1):
    print(text)
    time.sleep(seconds)

def title(text):
    clear_screen()
    width = shutil.get_terminal_size().columns
    print("=" * width)
    print(f"{text:^{width}}")
    print("=" * width)
    print()

def main_menu():
    while True:
        title(f"My Little Terminal v{VERSION} - Main Menu")
        hosts = load_hosts()
        favorites = [host for host in hosts if host.get("favorite", False)]
        host_names = {host["name"].lower(): host for host in hosts}

        if favorites:
            print("Favorites:")
            for idx, host in enumerate(favorites, start=1):
                print(f" [{idx}] {host['name']} ({host['ip']})")
            print()
    
        print("Menu:")
        print(" [h] Hosts")
        print(" [k] Keys")
        print(" [s] Snippets")
        print(" [i] Info & Support")
        print(" [q] Quit")
        print()
        choice = input("> Enter your choice: ").strip().lower()

        if choice == 'h':
            host_menu()
        elif choice == 'k':
            key_menu()
        elif choice == 's':
            snippet_menu()
        elif choice == 'i':
            update_menu()
        elif choice == 'q':
            message("Exiting the program.")
            sys.exit(0)
        elif choice.isdigit() and 1 <= int(choice) <= len(favorites):
            connect_host(favorites[int(choice) - 1])
        elif choice in host_names:
            connect_host(host_names[choice])
        else:
            message(f"{RED}Invalid choice. Please try again.{RESET}")

def build_remote_cmd():
    snippets = load_snippets()
    if not snippets:
        return None

    alias_lines = []
    for s in snippets:
        if "()" in s["cmd"]:
            alias_lines.append(s["cmd"])
        else:
            safe_cmd = s["cmd"].replace("'", "'\\''")
            alias_lines.append(f"alias {s['name']}='{safe_cmd}'")
    
    aliases_block = "\n".join(alias_lines)
    return (
        "cat << 'EOF' > /tmp/mylt_rc\n"
        "[ -f /etc/profile ] && . /etc/profile\n"
        "[ -f ~/.profile ] && . ~/.profile\n"
        "[ -f ~/.bashrc ] && . ~/.bashrc\n"
        f"{aliases_block}\n"
        "EOF\n"
        "if command -v bash >/dev/null 2>&1; then "
        "exec bash --rcfile /tmp/mylt_rc; "
        "else ENV=/tmp/mylt_rc exec sh; fi"
    )

def connect_host(host):
    if not host.get("user") or not host.get("ip"):
        message("Host information is incomplete. Please edit the host details.")
        return

    target = f"{host['user']}@{host['ip']}"
    port = str(host["port"])
    remote_cmd = build_remote_cmd()

    if remote_cmd:
        result = subprocess.run(["ssh", "-t", "-p", port, "-o", "HostKeyAlgorithms=+ssh-rsa", "-o", "PubkeyAcceptedAlgorithms=+ssh-rsa", target, remote_cmd])
    else:
        result = subprocess.run(["ssh", "-p", port, "-o", "HostKeyAlgorithms=+ssh-rsa", "-o", "PubkeyAcceptedAlgorithms=+ssh-rsa", target])

    if result.returncode == 255:
        err = subprocess.run(
            [
                "ssh",
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=2",
                "-o", "HostKeyAlgorithms=+ssh-rsa",
                "-p", port,
                target,
                "exit"
            ],
            capture_output=True, text=True
        ).stderr
        if "REMOTE HOST IDENTIFICATION HAS CHANGED" in err:
            print()
            if input("Do you want to remove the saved host key? (y/n): ").lower() == "y":
                rk_target = f"[{host['ip']}]:{port}" if port != "22" else host["ip"]
                subprocess.run(["ssh-keygen", "-R", rk_target])
                hosts = load_hosts()
                for h in hosts:
                    if h["ip"] == host["ip"] and h["port"] == host["port"] and h["user"] == host["user"]:
                        h["has_key"] = False
                save_hosts(hosts)

            
    message("Connection closed.")

def host_menu():
    while True:
        title(f"My Little Terminal v{VERSION} - Hosts")
        hosts = load_hosts()
        quick_select = {}
        if not hosts:
            print("No hosts available. Please add a host first.")
        else:
            for idx, host in enumerate(hosts, start=1):
                fav_marker = f"{MAGENTA} *{RESET}" if host.get("favorite", False) else ""
                print(f"[{idx}]{fav_marker} {host['name']} ({host['ip']})")
                quick_select[str(idx)] = host
                quick_select[host["name"].lower()] = host

        print()
        print("[a] Add Host")
        print("[e] Edit Host")
        print("[f] Mark/Unmark Favorite")
        print("[d] Delete Host")
        print("[b] Back to Main Menu")
        print()
        choice = input("> Enter your choice: ").strip().lower()

        if choice == 'a':
            add_host()
        elif choice == 'e':
            edit_host()
        elif choice == 'f':
            mark_favorite()
        elif choice == 'd':
            delete_host()
        elif choice == 'b':
            return
        elif choice in quick_select:
            connect_host(quick_select[choice])
        else:
            message(f"{RED}Invalid choice. Please try again.{RESET}")

def load_hosts():
    try:
        with open(HOSTS_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_hosts(hosts):
    with open(HOSTS_FILE, "w", encoding="utf-8") as file:
        json.dump(hosts, file, indent=4)

def add_host():
    title("Add Host or press CTRL+C for escape")
    try:
        name = input("Enter host name: ").strip()
        while True:
            ip = input("Enter host IP address: ").strip()
            if ip:
                break
            print("IP address cannot be empty!")
        while True:
            user = input("Enter username: ").strip()
            if user:
                break
            print("Username cannot be empty!")
        while True:
            port = input("Enter port (default 22): ").strip() or "22"
            if port.isdigit():
                break
            print("Invalid port. Please enter a valid port number.")
        favorite = input("Mark as favorite? (y/n): ").lower() == 'y'
    except KeyboardInterrupt:
        print()
        message("Operation cancelled.")
        return

    if not name:
        name = ip

    hosts = load_hosts()
    hosts.append({
        "name": name,
        "ip": ip,
        "user": user,
        "port": int(port),
        "favorite": favorite
    })
    save_hosts(hosts)
    message("Host saved!")

def edit_host():
    title("Edit Host or press CTRL+C for escape")
    hosts = load_hosts()
    if not hosts:
        message("No hosts available. Please add a host first.")
        return
    else:
        for idx, host in enumerate(hosts, start=1):
            print(f"[{idx}] {host['name']} ({host['ip']})")
        print("[b] Back")
        print()
        choice = input("> Enter the number of the host to edit: ").lower()
    if choice == 'b':
        return
    elif choice.isdigit() and 1 <= int(choice) <= len(hosts):
        selected_host = hosts[int(choice) - 1]
        try:
            name = input(f"Enter new name (current: {selected_host['name']}): ").strip() or selected_host['name']
            ip = input(f"Enter new IP (current: {selected_host['ip']}): ").strip() or selected_host['ip']
            user = input(f"Enter new username (current: {selected_host['user']}): ").strip() or selected_host['user']
            while True:
                port = input(f"Enter new port (current: {selected_host['port']}): ").strip() or str(selected_host['port'])
                if port.isdigit():
                    break
                print("Invalid port. Please enter a valid port number.")
        except KeyboardInterrupt:
            print()
            message("Operation cancelled.")
            return

        selected_host.update({
            "name": name,
            "ip": ip,
            "user": user,
            "port": int(port)
        })
        save_hosts(hosts)
        message("Host updated!")
    else:
        message(f"{RED}Invalid choice. Please try again.{RESET}")

def mark_favorite():
    title("Mark/Unmark Favorite")
    hosts = load_hosts()
    if not hosts:
        message("No hosts available. Please add a host first.")
        return
    else:
        for idx, host in enumerate(hosts, start=1):
            fav_marker = f"{MAGENTA} *{RESET}" if host.get("favorite", False) else ""
            print(f"[{idx}]{fav_marker} {host['name']} ({host['ip']})")

        print("[b] Back")
        print()
        choice = input("> Enter the number of the host to toggle favorite status: ").lower()

    if choice == 'b':
        return
    elif choice.isdigit() and 1 <= int(choice) <= len(hosts):
        selected_host = hosts[int(choice) - 1]
        selected_host["favorite"] = not selected_host.get("favorite", False)
        save_hosts(hosts)
        status = "marked as favorite" if selected_host["favorite"] else "unmarked as favorite"
        message(f"{selected_host['name']} has been {status}.")
    else:
        message(f"{RED}Invalid choice. Please try again.{RESET}")

def delete_host():
    title("Delete Host")
    hosts = load_hosts()
    if not hosts:
        message("No hosts available. Please add a host first.")
        return
    else:
        for idx, host in enumerate(hosts, start=1):
            print(f"[{idx}] {host['name']} ({host['ip']})")

        print("[b] Back")
        print()
        choice = input("> Enter the number of the host to delete: ").lower()

    if choice == 'b':
        return
    elif choice.isdigit() and 1 <= int(choice) <= len(hosts):
        selected_host = hosts[int(choice) - 1]
        confirm = input(f"Are you sure you want to delete {selected_host['name']}? (y/n): ").lower()
        if confirm == 'y':
            hosts.remove(selected_host)
            save_hosts(hosts)
            message("Host deleted!")
        else:
            message("Deletion canceled.")
    else:
        message(f"{RED}Invalid choice. Please try again.{RESET}")

def key_menu():
    key_path = os.path.expanduser("~/.ssh/id_rsa")

    while True:
        title(f"My Little Terminal v{VERSION} - Keys")
        print("[c] Create SSH Key")
        print("[s] Send Key to Host")
        print("[b] Back to Main Menu")
        print()
        choice = input("> Enter your choice: ").lower()

        if choice == 'c':
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            subprocess.run(["ssh-keygen", "-t", "rsa", "-b", "4096", "-f", key_path, "-N", ""])
            print()
            input("Press Enter to continue...")
        elif choice == 's':
            send_key_menu()
        elif choice == 'b':
            return
        else:
            message(f"{RED}Invalid choice. Please try again.{RESET}")

def send_key_menu():
    key_path = os.path.expanduser("~/.ssh/id_rsa")

    if not os.path.exists(f"{key_path}.pub"):
        message("No SSH public key found. Please create one first.")
        return

    hosts = load_hosts()
    if not hosts:
        message("No hosts available. Please add a host first.")
        return

    while True:
        title("Send Key to Host")
        hosts = load_hosts()
        for idx, host in enumerate(hosts, start=1):
            mark = f"{GREEN}x{RESET}" if host.get("has_key") else " "
            print(f"[{idx}] [{mark}] {host['name']} ({host['ip']})")
        print("[b] Back")
        print()
        choice = input("> Enter the number of the host to send key: ").lower()

        if choice == 'b':
            return
        elif choice.isdigit() and 1 <= int(choice) <= len(hosts):
            h = hosts[int(choice) - 1]
            pub_key = open(f"{key_path}.pub", encoding="utf-8").read().strip() + "\n"
            cmd = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
            result = subprocess.run(
                ["ssh", "-p", str(h["port"]), "-o", "HostKeyAlgorithms=+ssh-rsa", "-o", "PubkeyAcceptedAlgorithms=+ssh-rsa", f"{h['user']}@{h['ip']}", cmd],
                input=pub_key,
                text=True
            )
            if result.returncode == 0:
                h["has_key"] = True
                save_hosts(hosts)
            print()
            input("Press Enter to continue...")
        else:
            message(f"{RED}Invalid choice. Please try again.{RESET}")

def load_snippets():
    try:
        with open(SNIPPET_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_snippets(snippets):
    with open(SNIPPET_FILE, "w", encoding="utf-8") as file:
        json.dump(snippets, file, indent=4)

def snippet_menu():
    while True:
        title(f"My Little Terminal v{VERSION} - Snippets")
        snippets = load_snippets()
        if not snippets:
            print("No snippets available. Please add a snippet first.")
        else:
            for idx, snippet in enumerate(snippets, start=1):
                print(f"[{idx}] {snippet['name']}")
        print()
        print("Menu:")
        print("[a] Add Snippet")
        print("[e] Edit Snippet")
        print("[d] Delete Snippet")
        print("[b] Back to Main Menu")
        print()
        choice = input("> Enter your choice: ").lower()

        if choice == 'a':
            add_snippet()
        elif choice == 'e':
            edit_snippet()
        elif choice == 'd':
            delete_snippet()
        elif choice == 'b':
            return
        elif choice.isdigit() and 1 <= int(choice) <= len(snippets):
            selected_snippet = snippets[int(choice) - 1]
            message(f"{selected_snippet['name']} -> {selected_snippet['cmd']}", seconds=2)
        else:
            message(f"{RED}Invalid choice. Please try again.{RESET}")

def add_snippet():
    title("Add Snippet or press CTRL+C for escape")
    try:
        while True:
            name = input("Enter snippet name: ").strip()
            if name:
                break
            print("Snippet name cannot be empty!")
        while True:
            cmd = input("Enter command: ").strip()
            if cmd:
                break
            print("Command cannot be empty!")
    except KeyboardInterrupt:
        print()
        message("Operation cancelled.")
        return

    snippets = load_snippets()
    snippets.append({
        "name": name,
        "cmd": cmd
    })
    save_snippets(snippets)
    message("Snippet saved!")

def edit_snippet():
    title("Edit Snippet or press CTRL+C for escape")
    snippets = load_snippets()
    if not snippets:
        message("No snippets available.")
        return

    for idx, snippet in enumerate(snippets, start=1):
        print(f"[{idx}] {snippet['name']} -> {snippet['cmd']}")
    print()

    try:
        while True:
            choice = input("Enter snippet number to edit: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(snippets):
                snippet = snippets[int(choice) - 1]
                break
            print(f"{RED}Invalid choice. Please try again.{RESET}")

        name = input(f"Enter snippet name [{snippet['name']}]: ").strip() or snippet["name"]
        cmd = input(f"Enter command [{snippet['cmd']}]: ").strip() or snippet["cmd"]
    except KeyboardInterrupt:
        print()
        message("Operation cancelled.")
        return

    snippet["name"] = name
    snippet["cmd"] = cmd
    save_snippets(snippets)
    message("Snippet updated!")

def delete_snippet():
    title("Delete Snippet")
    snippets = load_snippets()
    if not snippets:
        message("No snippets available. Please add a Snippet first.")
        return
    else:
        for idx, snippet in enumerate(snippets, start=1):
            print(f"[{idx}] {snippet['name']} -> {snippet['cmd']}")

        print("[b] Back")
        print()
        choice = input("> Enter the number of the snippet to delete: ").lower()

    if choice == 'b':
        return
    elif choice.isdigit() and 1 <= int(choice) <= len(snippets):
        selected_snippet = snippets[int(choice) - 1]
        confirm = input(f"Are you sure you want to delete {selected_snippet['name']}? (y/n): ").lower()
        if confirm == 'y':
            snippets.remove(selected_snippet)
            save_snippets(snippets)
            message("Snippet deleted!")
        else:
            message("Deletion canceled.")
    else:
        message(f"{RED}Invalid choice. Please try again.{RESET}")

def update_menu():
    while True:
        title(f"My Little Terminal v{VERSION} - Info & Support")
        print("[c] Check for New Version")
        print("[s] Open Support Forum")
        print("[b] Back to Main Menu")
        print()
        choice = input("> Enter your choice: ").lower()

        if choice == 'c':
            check_updates()
        elif choice == 's':
            message(f"Opening {GREEN}https://www.boxpirates.to{RESET} in browser...")
            webbrowser.open("https://www.boxpirates.to")
        elif choice == 'b':
            return
        else:
            message(f"{RED}Invalid choice. Please try again.{RESET}")

    
def check_updates():
    title("Version Check")
    print(f"Installed version: v{VERSION}")
    print("Checking GitHub for latest release...")
    print()

    url = "https://api.github.com/repos/d4n13l13/mylt/releases/latest"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mylt-updater"})
        context = ssl.create_default_context(cafile=certifi.where()) if certifi else None
        with urllib.request.urlopen(req, context=context, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            latest = data.get("tag_name", "").lstrip("v")

            if not latest:
                print("Could not determine latest version.")
            elif latest == VERSION:
                print("You are already using the latest version!")
            else:
                download_url = data.get("html_url", "")
                print(f"New version available: v{latest}")
                if download_url:
                    print(f"Download: {GREEN}{download_url}{RESET}")
                    webbrowser.open(download_url)
    except Exception:
        print("Could not check for new version (offline or repository not published yet).")

    print()
    input("Press Enter to continue...")


if __name__ == "__main__":
    main_menu()
