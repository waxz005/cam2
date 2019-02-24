import socket
import struct
ip = '192.168.100.105'
port = 10005

GET0FRAME = 0
GET1FRAME = 2
GETMFRAME = 1
parafmt = 'iiiiiii'

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client.connect((ip, port))
cnt = 0

def sendcmd(cmd):
    client.send(struct.pack('i', cmd))
    recv = struct.unpack(parafmt, client.recv(65536))
    return recv
def test():
    for i in range(1):
        client.send(struct.pack('i', 2))
        recv = struct.unpack(parafmt, client.recv(65536))
        print(recv)
        client.send(struct.pack('i', 1))
        recv = struct.unpack(parafmt, client.recv(65536))
        print(recv)
        client.send(struct.pack(parafmt, 1,2,3,4,5,6,7))
        recv = struct.unpack(parafmt, client.recv(65536))
        print('send')
        if recv != (1,2,3,4,5,6,7):
            cnt += 1
    print(recv, cnt)

if __name__ == '__main__':
    sendcmd(0)
    # client.send(struct.pack('i', 2))
    # recv = struct.unpack(parafmt, client.recv(65536))
    # f = open('./1.png', 'wb')
    # cnt = 0
    # while 1:
    #     cnt += 1
    #     # print(cnt)
    #     data, addr = client.recvfrom(1024)
    #     print(len(data))
    #     if len(data)==3:
    #         print(data)
    #     if data != b'end':
    #         f.write(data)
    #     else:
    #         print('ok')
    #         break
    # f.close()
    # print("recv depth image success")

