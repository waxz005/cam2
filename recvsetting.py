import socket
import struct
import threading
import cv2
import numpy
import datetime
import time
import configparser

HOST = '127.0.0.1'    # 图像发送地址-主机ip
PORT = 9902           # 图像发送端口
sendserver = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
sendserver.connect((HOST, PORT))
cap = cv2.VideoCapture(0)
HOSTlocal = '127.0.0.1'   # 命令接收地址
PORTlocal = 10002         # 命令接收端口
server = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
server.bind((HOSTlocal, PORTlocal))
server.setblocking(0)
GET0FRAME = 0
GET1FRAME = 2
GETMFRAME = 1
SETTINGRECT = 3
TESTCODE = 4
CLEAR = 1
NOTCLEAR = 0
getframe = GET0FRAME
isClear = 1
parameterfmt = 'iiiiiii'

class sendImageThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.cnt = 0
    def run(self):
        global getframe
        global isClear
        while(1):
            if(getframe == GET1FRAME):
                frame = []
                for i in range(10):
                    suc, frame = cap.read()
                #cv2.imshow("1", frame)
                #cv2.waitKey(1)
                result,imgencode=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,50])
                sendserver.sendall(struct.pack('i',imgencode.shape[0]))                
                sendserver.sendall(struct.pack('i',CLEAR)) #  if bad send 0,else send 1
                sendserver.sendall(imgencode)
                getframe = GET0FRAME             
                print('send a frame')
                continue
            if(getframe == GETMFRAME):
                time.sleep(0.05)
                suc, frame = cap.read()
                result,imgencode=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,50])
                sendserver.sendall(struct.pack('i',imgencode.shape[0]))
                sendserver.sendall(struct.pack('i',isClear)) #  if bad send 0,else send 1
                sendserver.sendall(imgencode)


sthread = sendImageThread()
sthread.start()

def readparameter(file):
    conf = configparser.ConfigParser()
    conf.read(file)
    LT_x = conf.getint("setting", "LT_x")
    LT_y = conf.getint("setting", "LT_y")
    RB_x = conf.getint("setting", "RB_x")
    RB_y = conf.getint("setting", "RB_y")
    Bad_Width = conf.getint("setting", "Bad_Width")
    Bad_Height = conf.getint("setting", "Bad_Height")
    Std_Height = conf.getint("setting", "Std_Height")
    return (LT_x, LT_y, RB_x, RB_y, Bad_Width, Bad_Height, Std_Height)

def saveparameters(data):
    if len(data) != len(parameterfmt):
        return -1
    conf = configparser.ConfigParser()
    conf.read('./setting.cfg')
    LT_x, LT_y, RB_x, RB_y, Bad_Width, Bad_Height, Std_Height = data
    conf.set("setting", "LT_x", str(LT_x))
    conf.set("setting", "LT_y", str(LT_y))
    conf.set("setting", "RB_x", str(RB_x))
    conf.set("setting", "RB_y", str(RB_y))
    conf.set("setting", "Bad_Width", str(Bad_Width))
    conf.set("setting", "Bad_Height", str(Bad_Height))
    conf.set("setting", "Std_Height", str(Std_Height))
    conf.write(open('./setting.cfg', 'w'))

def func(isclear):
    global getframe
    global isClear
    isClear = isclear
    # print(isClear)
    # while 1:
    try:
        data, addr = server.recvfrom(65536)
        if len(data) == len(parameterfmt)*4:  #  setting rect
            recv = struct.unpack(parameterfmt, data)
            print('recv setting', recv)
            saveparameters(recv)
            server.sendto(struct.pack(parameterfmt,*recv), addr)
            recv = list(recv)
            recv.append(SETTINGRECT)
            return tuple(recv)  # 3 for setting
        elif len(data) == 4 and struct.unpack('i', data)[0] == GET0FRAME: # if recv work
            print('recv GET0FRAME')
            getframe = GET0FRAME
            ret = (0,0,0,0,0,0,0, GET0FRAME)
            server.sendto(struct.pack(parameterfmt,*ret[:-1]), addr)
            return ret
        elif len(data) == 4 and struct.unpack('i', data)[0] == GETMFRAME: # if recv work
            print('recv GETMFRAME')
            getframe = GETMFRAME
            ret = (1,1,1,1,1,1,1, GETMFRAME)
            server.sendto(struct.pack(parameterfmt,*ret[:-1]), addr)
            return ret
        elif len(data) == 4 and struct.unpack('i', data)[0] == GET1FRAME: # if recv get1frame
            print('recv GET1FRAME')
            getframe = GET1FRAME
            ret = (2,2,2,2,2,2,2, GET1FRAME)
            server.sendto(struct.pack(parameterfmt,*ret[:-1]), addr)
            return ret
        elif len(data) == 4 and struct.unpack('i', data)[0] == TESTCODE: # if recv get1frame
            print('recv TESTCODE')
            getframe = GETMFRAME
            isClear = 1 - isClear
            print(isClear)
            ret = (1,1,1,1,1,1,1, GETMFRAME)
            server.sendto(struct.pack(parameterfmt,*ret[:-1]), addr)
            return ret
        else:
            print('no-def cmd')
            ret = (-1,-1,-1,-1,-1,-1,-1,-1)
            server.sendto(struct.pack(parameterfmt,*ret[:-1]), addr)
            return ret  # -1 for no-def cmd
    except:
        return (-1,-1,-1,-1,-1,-1,-1,-1)  # non-blocking recv, return -1

def main():
    global isClear
    while(1):
        recv = func(isClear)
        # print('waiting')
        if -1 in recv:
            continue
        print(recv)

if __name__ == '__main__':
    main()
