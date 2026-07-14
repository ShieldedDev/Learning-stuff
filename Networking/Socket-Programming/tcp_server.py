import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('0.0.0.0', 9999))
server.listen(5)
print("[*] Listening on port 9999")

client_socket, addr = server.accept()
print(f"[*] Accepted connection from {addr}")

client_socket.send(b"Hello from server!")
client_socket.close()
