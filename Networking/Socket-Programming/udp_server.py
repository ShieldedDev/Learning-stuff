import socket

host = "127.0.0.1"  # Listen on localhost
port = 4444

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((host, port))  # Bind the socket to an address and port

print(f"UDP server listening on {host}:{port}")

while True:
    data, addr = sock.recvfrom(1024)  # Receive data and sender's address
    print(f"Received message: {data.decode()} from {addr}")
    # Optional: Send a response back
    sock.sendto(b"Echo: " + data, addr) 
