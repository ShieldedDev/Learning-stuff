import threading
from scapy.all import IP, TCP, sr1

def scan_port(ip, port):
    pkt = IP(dst=ip)/TCP(dport=port, flags='S')
    resp = sr1(pkt, timeout=0.5, verbose=0)
    if resp and resp.haslayer(TCP) and resp[TCP].flags == 0x12:
        print(f"[+] Port {port} open on {ip}")

target = '192.168.1.10'
ports = range(20, 1025)

for p in ports:
    t = threading.Thread(target=scan_port, args=(target, p))
    t.start()
    
