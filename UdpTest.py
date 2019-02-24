import socket

address = ('127.0.0.1', 1001)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(address)

while (True):
    try:
        data, addr = s.recvfrom(8)
        if not data:
            print ('client has exist')
            break
        print ('received:', data, 'from', addr)
    except:
        print ('udp server error')

s.close()
