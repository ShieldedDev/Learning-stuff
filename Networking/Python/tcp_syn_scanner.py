from scapy.all import IP, TCP, sr1

target = "192.168.1.10"
ports = [22, 80, 443]

for port in ports:
    pkt = IP(dst=target)/TCP(dport=port, flags='S')
    resp = sr1(pkt, timeout=1, verbose=0)
    if resp and resp.haslayer(TCP):
        if resp[TCP].flags == 0x12:
            print(f"Port {port} is open")
        elif resp[TCP].flags == 0x14:
            print(f"Port {port} is closed")
    
