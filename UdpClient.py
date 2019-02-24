import socket
import struct

address = ('127.0.0.1', 1000)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

while True:
    msg = input()
    if not msg:
        break
    # s.sendto(msg.encode(), address)
    s.sendto(struct.pack('i', int(msg.encode())), address)

s.close()