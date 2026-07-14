import socket

host = "127.0.0.1"  # Server IP address
port = 4444
MESSAGE = b"Hello, UDP Server!"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(MESSAGE, (host, port))  # Send data to the server

# Optional: Receive a response from the server
data, addr = sock.recvfrom(1024)
print(f"Received response: {data.decode()} from {addr}")

sock.close()
