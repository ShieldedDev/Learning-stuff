from scapy.all import *

target = "192.168.1.10"

for port in range(1, 1025):

    packet = IP(dst=target)/TCP(dport=port, flags="S")

    response = sr1(packet, timeout=1, verbose=0)

    if response:

        if response.haslayer(TCP):

            if response[TCP].flags == 0x12:
                print(f"Port {port} is OPEN")

                send(IP(dst=target)/TCP(dport=port, flags="R"), verbose=0)
