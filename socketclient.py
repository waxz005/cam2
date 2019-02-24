import cv2
import numpy
import socket
import struct
import datetime

HOST='192.168.1.112'
PORT=9991
buffSize=65535
cnt = 0

server=socket.socket(socket.AF_INET,socket.SOCK_DGRAM) #创建socket对象
server.bind((HOST,PORT))
print('now waiting for frames...')
while True:
    cnt += 1
    print(cnt)
    data,address=server.recvfrom(buffSize) #先接收的是字节长度
    if len(data)==2 and data==b'ok':
        print('clear!!!')
    if len(data)==1 and data[0]==1: #如果收到关闭消息则停止程序
        server.close()
        cv2.destroyAllWindows()
        exit()
    if len(data)!=4: #进行简单的校验，长度值是int类型，占四个字节
        length=0
    else:
        length=struct.unpack('i',data)[0] #长度值
    data,address=server.recvfrom(buffSize) #接收编码图像数据
    if length!=len(data): #进行简单的校验
        continue
    data=numpy.array(bytearray(data)) #格式转换
    imgdecode=cv2.imdecode(data,1) #解码
    print('warning!!!')
    print(datetime.datetime.now())
    cv2.imshow('frames',imgdecode) #窗口显示
    if cv2.waitKey(1)==27: #按下“ESC”退出
        break
server.close()
cv2.destroyAllWindows()
