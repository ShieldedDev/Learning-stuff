from scapy.all import ICMP, IP, sr1

subnet = '192.168.1.'
for i in range(1, 255):
    ip = subnet + str(i)
    pkt = IP(dst=ip)/ICMP()
    reply = sr1(pkt, timeout=0.5, verbose=0)
    if reply:
        print(f"Host {ip} is alive")
    
