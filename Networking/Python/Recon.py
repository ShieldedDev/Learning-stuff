import socket
import threading
import requests
import nmap

TARGET = "192.168.1.10"

OPEN_PORTS = []

def port_scan(port):

    sock = socket.socket()

    sock.settimeout(1)

    result = sock.connect_ex((TARGET, port))

    if result == 0:

        OPEN_PORTS.append(port)

        print(f"[+] Port {port} OPEN")

    sock.close()

for port in range(1, 1025):

    thread = threading.Thread(target=port_scan, args=(port,))

    thread.start()

scanner = nmap.PortScanner()

scanner.scan(TARGET, arguments="-sV")

for host in scanner.all_hosts():

    for proto in scanner[host].all_protocols():

        ports = scanner[host][proto].keys()

        for port in ports:

            service = scanner[host][proto][port]

            print(f"""

Port: {port}
Service: {service['name']}
Product: {service.get('product')}
Version: {service.get('version')}

""")

try:

    response = requests.get(f"http://{TARGET}", timeout=3)

    print(response.headers)

except:
    pass
