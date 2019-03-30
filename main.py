# -*- coding: utf-8 -*-
# 主文件，实现主界面的函数

import sys, os, serial
from PyQt5 import QtWidgets, QtCore, QtGui
from MainWindow import Ui_Form
from setroidlg import Ui_Dlg_setroi
from PyQt5.QtCore import QThread, QEvent, QTimer
from PyQt5.QtGui import QImage, QPixmap
import cv2
import numpy as np
import socket
import struct
import datetime
import configparser
import threading
import time
import wmi

DiskNumber = '002810300A07'
# if wmi.WMI().Win32_DiskDrive()[0].SerialNumber.strip() != DiskNumber:
#     print("硬件设备故障，程序终止")
#     time.sleep(3)
#     # os._exit(0)
# Initialtime = datetime.datetime(2019,3,11)
# if (datetime.datetime.now() - Initialtime).days>7:
#     print("超时未注册，退出程序")
#     # os._exit(0)

GET0FRAME = 0
GET1FRAME = 2
GETMFRAME = 1
SETTINGRE = 3
CAMERROR = 5
SAVEBKIMG = 6
CAMONLINE = 10
CAMOFLINE = 20
parameterfmt = 'iiiiiii'

# 测试用数据
HOST = '127.0.0.1'
PORT = 9999
buffSize = 65535
cnt = 0
global imgtest

# 保存背景全局变量
BKFILE = "./imagebk/background{}.png"
imageblack = np.zeros((480, 640), np.uint8)
imageblack = QImage(imageblack.data, imageblack.shape[1], imageblack.shape[0], QImage.Format_Grayscale8)
imagegray = np.ones((480, 640), np.uint8)
imagegray = QImage(imagegray.data, imagegray.shape[1], imagegray.shape[0], QImage.Format_Grayscale8)
# 测试用数据结束
# 图像全局变量，socket接收到数据后存入其中，并发送signal
# 预置了30个640*480*3大小的u8类型图像文件，后续需要还可以继续扩充
imgdecode = [np.zeros((480, 640, 3), np.uint8)] * 31

# 串口接收命令定义
#SERCMD_OPEN = b'\x55\xaa\x01\x00\x00\x00\xeb\x90'  # 正常状态 已经取消该状态
# SERCMD_CLOS = b'\x55\xaa\x02\x00\x00\x00\xeb\x90'   # 上下行人状态
# SERCMD_DETE = b'\x55\xaa\x01\x00\x00\x00\xeb\x90'   # 检测状态
SERCMD_CLOS = 2   # 上下行人状态
SERCMD_DETE = 1   # 检测状态
SERCMD_4 = b'\x55\xaa\x04\x00\x00\x00\xeb\x90'
SERCMD_5 = b'\x55\xaa\x05\x00\x00\x00\xeb\x90'
# SERCMD_6 = b'\x55\xaa\x06\x00\x00\x00\xeb\x90'      # 复位状态，停止检测，清除报警，显示蓝色
SERCMD_6 = 6      # 复位状态，停止检测，清除报警，显示蓝色
SERCMD_7 = b'\x55\xaa\x07\x00\x00\x00\xeb\x90'
SERCMD_8 = b'\x55\xaa\x08\x00\x00\x00\xeb\x90'
# 串口发送命令定义
SERCMD_BAD = b'\x55\xaa\x10\x00\x00\x00\xeb\x90'  # 有异物
SERCMD_OK  = b'\x55\xaa\x20\x00\x00\x00\xeb\x90'  # 无异物

class MSerialPort(QtCore.QObject):
    SerRecieved = QtCore.pyqtSignal(int)
    state = True
    def __init__(self, port, baud):
        super(MSerialPort, self).__init__()
        self.comm = serial.Serial(port, baud)
        self.comm.close()
        if not self.comm.isOpen():
            self.comm.open()

    def port_open(self):
        if not self.comm.isOpen():
            self.comm.open()

    def port_close(self):
        self.comm.close()

    def send_data(self, data):
        number = self.comm.write(data)
        return number

    def read_data(self):
        while True:
            if self.state == True:
                data = self.comm.readline()
                if data[:2] == b'\x55\xaa':
                    self.recv_data = data[2]
                    print (self.recv_data)
                    self.SerRecieved.emit(1)
                else:
                    self.recv_data = None
                    print (self.recv_data)

#
# class Serial_D(QtCore.QObject):
#     SerRecieved = QtCore.pyqtSignal(int)
#     def __init__(self, port="COM1",bps=9600):
#         super(Serial_D, self).__init__()
#         self.port = port
#         self.bps = bps
#         self.recv_data = None
#         self.timer = QTimer()
#         self.timer.timeout.connect(self.recieve)
#         try:
#             self.ser = serial.Serial(self.port, self.bps)
#         except:
#             raise serial.portNotOpenError
#             print("串口打开失败！")
#
#     def get_recv_data(self):
#         return self.recv_data
#
#     def recieve(self):
#         # print(1)
#         num = 0
#         try:
#             num = self.ser.inWaiting()
#         except:
#             self.recv_data = None
#         if num>0:
#             data = self.ser.read(num)
#             # print('received: ',data)
#             num = len(data)
#             if data[:2]==b'\x55\xaa' and data[-2:]==b'\xeb\x90':
#                 self.recv_data = data
#                 self.SerRecieved.emit(1)
#             else:
#                 self.recv_data = None
#
#     def send_data(self,data):
#         if type(data) != bytes:
#             data = data.encode()
#         try:
#             num = self.ser.write(data)
#             #print(num)
#             if num == 8:
#                 return True
#             else:
#                 return False
#         except:
#             return False


# 接收图像的线程类
class RecImgThread(QThread):
    # signal，若没有异物，返回0；有返回1
    isClear = QtCore.pyqtSignal(int)
    # host：上位机IP
    # port: 端口号
    # index: 序号，接收第index个下位机传输的数据
    def __init__(self, addr = ('127,0.0.1', 9900), index=0, parent=None):
        super(RecImgThread, self).__init__(parent)
        # self.working = True # 工作状态，暂时没用
        self.num = 0
        self.addr = addr
        self.index = index
        self.buffsize = 65535
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server.bind(self.addr)
            self.server.settimeout(6)
            self.working = True
        except:
            self.server = None
            self.working = False

    def __del__(self):
        self.working = False
        self.wait()

    def stop(self):
        self.working = False
        self.server.close()
        cv2.destroyAllWindows()
        self.terminate()

    def run(self):
        while self.working:
            try:
                # if not self.working: return
                # 第一次接收到的数据，根据协议，为数据长度
                data, address = self.server.recvfrom(self.buffsize)
                if len(data) == 4 and struct.unpack('i', data)[0] == CAMONLINE:
                    self.isClear.emit(CAMONLINE)
                    continue
                    # pass
                if len(data) == 4 and struct.unpack('i', data)[0] == CAMERROR:
                    self.working = False
                    self.isClear.emit(CAMERROR)
                if len(data) != 4:  # 进行简单的校验，长度值是int类型，占四个字节
                    length = 0
                    continue  # 加上之后容错能力更强，否则容易卡顿
                else:
                    length = struct.unpack('i', data)[0]  # struct返回tuple，[0]取第一个数，即长度值
                data, address = self.server.recvfrom(self.buffsize)
                # 第2次接收数据，根据协议，为是否有异物标志，0表示有异物
                if len(data) != 4:  # 进行简单的校验，长度值是int类型，占四个字节
                    isClear = 1
                    continue  # 加上之后容错能力更强，否则容易卡顿
                else:
                    isClear = struct.unpack('i', data)[0] # 接收是否有异物的信息，0表示有异物
                # print(isClear)
                data, address = self.server.recvfrom(self.buffsize)  # 接收编码图像数据
                if length != len(data):  # 进行简单的校验
                    # 测试用，出现掉帧情况时，控制台输出警告词语
                    print('one frame is lost!!!', self.num)
                    self.num += 1    # 暂时没想好干什么用
                    #print(self.num)  # 暂时用于统计掉帧个数，但不完整，因为length和isClear也有掉帧，并未统计在内
                    continue         # 加上之后容错能力更强，否则容易卡顿
                data = np.array(bytearray(data))  # 格式转换
                global imgdecode  # 声明使用全局变量
                global imgtest    # 测试用全局变量
                imgdecode[self.index] = cv2.imdecode(data, 1)  # 解码
                cv2.cvtColor(imgdecode[self.index], cv2.COLOR_BGR2RGB, imgdecode[self.index])
                # 如果有异物，发出信号0，否则发出-1
                if isClear == 0:
                    self.isClear.emit(0)   # 释放signal，触发slot函数处理
                else:
                    self.isClear.emit(1)  # 释放signal，触发slot函数处理
                # imgtest = cv2.imdecode(data, 1)
                # print('warning!!!')
                # print(datetime.datetime.now())
                # cv2.imshow('frames', imgdecode)  # 窗口显示
                # if cv2.waitKey(1) == 27:  # 按下“ESC”退出，测试用
                    # break
            except:
                self.isClear.emit(CAMOFLINE)

# 设置子界面
class SetDlg(QtWidgets.QDialog, Ui_Dlg_setroi):
    def __init__(self, image, index, addr):
        super(SetDlg, self).__init__()
        self.setupUi(self)
        self.label_imgsw.installEventFilter(self)
        self.label_index_sw.setText(str(index))
        self.lineEdit_LT_x.setValidator(QtGui.QIntValidator(1,640,self))
        self.lineEdit_LT_y.setValidator(QtGui.QIntValidator(1,480,self))
        self.lineEdit_RB_x.setValidator(QtGui.QIntValidator(1,640,self))
        self.lineEdit_RB_y.setValidator(QtGui.QIntValidator(1,480,self))
        #self.label_index_sw.setStyleSheet("color:red")

        #
        self.addr = addr
        self.server_cmd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_cmd.connect(addr)
        # print(host, port)

        self.index = index  # 需要设置的前端序号
        # 显示图片
        self.image = np.zeros((480, 640, 3), np.uint8)
        self.depth = np.zeros((480, 640), np.uint16)
        imgheight = self.image.shape[0]  # 获取图像高度，默认480
        imgwidth = self.image.shape[1]   # 获取图像宽度，默认640
        self.HScale = imgheight / (self.label_imgsw.height()-1)  # 计算高度放大倍数
        self.WScale = imgwidth / (self.label_imgsw.width()-1)    # 计算宽度放大倍数

        # imgsw = QImage(self.image.data, self.image.shape[1], self.image.shape[0], QImage.Format_RGB888)
        # imgsw = QImage(imgtest.data, imgtest.shape[1], imgtest.shape[0], QImage.Format_RGB888)
        self.label_imgsw.setScaledContents(True)  # 设置自适应大小，否则只显示部分
        self.label_imgsw.setPixmap(QPixmap.fromImage(imageblack))

        # 读取已有配置文件
        self.conf = configparser.ConfigParser()
        self.conf.read("./config.cfg")
        self.machine = "machine"+str(index)
        # 读取该前端上一次参数并显示
        self.parafmt = parameterfmt  # 参数pack格式，与parameter对应
        LT_x = self.conf.getint(self.machine, "LT_x")
        LT_y = self.conf.getint(self.machine, "LT_y")
        RB_x = self.conf.getint(self.machine, "RB_x")
        RB_y = self.conf.getint(self.machine, "RB_y")
        Bad_Height = self.conf.getint(self.machine, "Bad_Height")
        Bad_Width = self.conf.getint(self.machine, "Bad_Width")
        Std_Height = self.conf.getint(self.machine, "Std_Height")
        self.lineEdit_LT_x.setText(str(LT_x))
        self.lineEdit_LT_y.setText(str(LT_y))
        self.lineEdit_RB_x.setText(str(RB_x))
        self.lineEdit_RB_y.setText(str(RB_y))
        self.lineEdit_badHeight.setText(str(Bad_Height))
        self.lineEdit_badWidth.setText(str(Bad_Width))
        self.lineEdit_stdHeight.setText(str(Std_Height))

    # 鼠标事件处理
    def eventFilter(self, obj, event):
        if obj == self.label_imgsw:
            # if event.type() == QEvent.MouseButtonDblClick:
            #     self.textEdit_information.setText("双击了Label")
            if event.type() == QEvent.MouseButtonPress:
                x = event.pos().x() * self.HScale
                y = event.pos().y() * self.WScale
                dep = self.depth[int(y)][int(x)]
                self.textEdit_information.setText('X: %d; Y: %d; 高度: %d' % (x, y, dep))
                # self.textEdit_information.setText("按下了鼠标")
            # elif event.type() == QEvent.MouseButtonRelease:
            #     self.textEdit_information.setText("释放了鼠标")
            # elif event.type() == QEvent.MouseMove:
            #     x = event.pos().x()*self.HScale
            #     y = event.pos().y()*self.WScale
            #     dep = self.depth[int(y)][int(x)]
            #     self.textEdit_information.setText('X: %d; Y: %d; DEPTH: %d' % (x, y, dep))
        # 必须有，否则打不开界面
        return super(SetDlg, self).eventFilter(obj, event)

    def check_input_LT_x(self):
        strtmp = self.lineEdit_LT_x.text()
        if strtmp:
            value = int(strtmp)
            # 如果小于0，设置为0
            if value <= 0:
                self.lineEdit_LT_x.setText("0")
            elif str(value) != strtmp:
                self.lineEdit_LT_x.setText(str(value))

    def check_input_LT_y(self):
        strtmp = self.lineEdit_LT_y.text()
        if strtmp:
            value = int(strtmp)
            # 如果小于0，设置为0
            if value <= 0:
                self.lineEdit_LT_y.setText("0")
            elif str(value) != strtmp:
                self.lineEdit_LT_y.setText(str(value))

    def check_input_RB_x(self):
        strtmp = self.lineEdit_RB_x.text()
        if strtmp:
            value = int(strtmp)
            # 如果小于0，设置为0
            if value <= 0:
                self.lineEdit_RB_x.setText("0")
            elif str(value) != strtmp:
                self.lineEdit_RB_x.setText(str(value))

    def check_input_RB_y(self):
        strtmp = self.lineEdit_RB_y.text()
        if strtmp:
            value = int(strtmp)
            # 如果小于0，设置为0
            if value <= 0:
                self.lineEdit_RB_y.setText("0")
            elif str(value) != strtmp:
                self.lineEdit_RB_y.setText(str(value))

    # 预览设置
    def pre_setting(self):
        LT_x, LT_y, RB_x, RB_y, Bad_Width, Bad_Height, Std_Height = self.CheckSetInput()
        if -1 in (LT_x, LT_y, RB_x, RB_y, Bad_Width, Bad_Height, Std_Height):
            return
        # 画出区域
        image = self.image.copy()
        roi = self.depth[LT_y:RB_y, LT_x:RB_x].copy()
        roimax = roi.max()
        roimin = roi.min()
        roimean = int(roi.mean())
        area = self.isClear3()
        if area == -1:
            self.textEdit_information.setText("背景图像不存在，请保存背景后再预览设置")
            return
        # refcnt = np.sum((roi<Std_Height-Bad_Height))
        refcnt = int(np.sqrt(area+100))
        self.textEdit_information.setText("区域最远:{} 区域最近:{} 区域均值:{}".format(roimax, roimin,int(roimean)))
        self.textEdit_information.insertPlainText("建议设置：异物宽度 {}像素 || 异物高度 {}mm || 标准高度 {}mm\n".format(refcnt,150,int(roimax*0.97)))
        self.textEdit_information.insertPlainText("距离:{} 面积:{}\n".format(roimean, area))
        # cv2.imshow('1', image[LT_y:RB_y,LT_x:RB_x]);cv2.waitKey(0)
        # 画矩形
        cv2.rectangle(image, (LT_x, LT_y), (RB_x, RB_y), (50, 200, 127), 3)
        # 减少固定值
        num = np.zeros(image[LT_y:RB_y, LT_x:RB_x].shape, image.dtype) + 50
        image[LT_y:RB_y, LT_x:RB_x] = cv2.subtract(image[LT_y:RB_y, LT_x:RB_x], num)
        #image[LT_x:RB_x, LT_y:RB_y] = cv2.addWeighted(image[LT_x:RB_x, LT_y:RB_y], 0.5, [255, 255, 255], 0.5)

        imgsw = QImage(image.data, image.shape[1], image.shape[0], QImage.Format_RGB888)
        self.label_imgsw.setPixmap(QPixmap.fromImage(imgsw))

    # 保存背景图像在上位机（用于算法调试）和前端
    def savebkimage(self):
        cv2.imwrite(BKFILE.format(self.index), self.depth)
        self.server_cmd.settimeout(5)
        try:
            self.server_cmd.send(struct.pack('i', SAVEBKIMG))
            data = self.server_cmd.recv(256)
            if data[0] == SAVEBKIMG:
                QtWidgets.QMessageBox.information(self,"提示","保存成功",QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No)
        except:
            QtWidgets.QMessageBox.warning(self, "提示", "保存失败，请重新保存！", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

    # 使用标准深度法检测
    def isClear2(self):
        LT_x, LT_y, RB_x, RB_y, Bad_Width, Bad_Height, Std_Height = self.CheckSetInput()
        if -1 in (LT_x, LT_y, RB_x, RB_y, Bad_Width, Bad_Height, Std_Height):
            return
        roi = self.depth[LT_y:RB_y, LT_x:RB_x].copy()
        # cv2.convertScaleAbs(roi,roi,1/roimax)
        roi[np.where(roi > Std_Height * 0.99)] = Std_Height
        roi[np.where(roi <= 0)] = Std_Height
        roi = Std_Height - roi
        cv2.blur(roi, (11, 11), roi)
        cv2.convertScaleAbs(roi, roi, 255. / (Bad_Height + 1))
        th, roi = cv2.threshold(roi, 255 * 0.5, 255, cv2.THRESH_BINARY)
        # print(roi.max(),roi.min())
        roi = roi.astype(np.uint8)
        cv2.imshow("roi", roi)
        cv2.waitKey(1)
        kernel = np.ones((3, 3), np.uint8)
        roi = cv2.dilate(roi, kernel)
        _, contours, h = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        area = 0
        for i in range(len(contours)):
            cnt = cv2.contourArea(contours[i])
            if area < cnt:
                area = cnt
        return area
    # 使用背景减除算法检测
    def isClear3(self):
        LT_x, LT_y, RB_x, RB_y, Bad_Width, Bad_Height, Std_Height = self.CheckSetInput()
        if -1 in (LT_x, LT_y, RB_x, RB_y, Bad_Width, Bad_Height, Std_Height):
            return
        filename = "./imagebk/background{}.png".format(self.index)
        if os.path.exists(filename)==False:
            return -1
        background = cv2.imread(filename,cv2.IMREAD_UNCHANGED)
        roi = self.depth[LT_y:RB_y,LT_x:RB_x].copy()
        bkroi = background[LT_y:RB_y,LT_x:RB_x].copy()
        if Bad_Height < 20: Bad_Height = 20
        if Bad_Height > 200: Bad_Height = 200
        # 将roi和bkroi中小于500，大于标准高度0.99的均设为0，不进行处理
        # roi中小于500和大于标高的区域设为0
        roi[np.where(roi<=500)]=0
        roi[np.where(roi>Std_Height*0.99)]=0
        # roi中bkroi小于500和大于标高的对应区域设为0
        roi[np.where(bkroi <= 500)] = 0
        roi[np.where(bkroi > Std_Height * 0.99)] = 0
        # bkroi中roi为0的对应区域设为0，去除不稳定0值区域的干扰
        bkroi[np.where(roi==0)]=0
        cv2.absdiff(bkroi, roi, roi)

        cv2.blur(roi,(11,11),roi)
        cv2.convertScaleAbs(roi, roi, 255./(Bad_Height+1))
        th, roi = cv2.threshold(roi,255*0.5,255,cv2.THRESH_BINARY)
        roi = roi.astype(np.uint8)
        cv2.imshow("roi", roi)
        cv2.waitKey(1)
        kernel = np.ones((3, 3), np.uint8)
        roi = cv2.dilate(roi, kernel)
        if cv2.__version__ == '4.0.0':
            contours, h = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        else:
            _, contours, h = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        area = 0
        for i in range(len(contours)):
            cnt = cv2.contourArea(contours[i])
            if area < cnt:
                area = cnt
        return area

    # 检测设置框内容并返回
    def CheckSetInput(self):
        # 检查输入是否有问题，尚不完备
        LT_x, LT_y, RB_x, RB_y, Bad_Width, Bad_Height, Std_Height=(-1,)*7
        try:
            # 读取参数
            LT_x = int(self.lineEdit_LT_x.text())
            LT_y = int(self.lineEdit_LT_y.text())
            RB_x = int(self.lineEdit_RB_x.text())
            RB_y = int(self.lineEdit_RB_y.text())
            Bad_Width = int(self.lineEdit_badWidth.text())
            Bad_Height = int(self.lineEdit_badHeight.text())
            Std_Height = int(self.lineEdit_stdHeight.text())
        except:
            QtWidgets.QMessageBox.warning(self, "警告", "坐标值不能为空！", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            return (-1,)*7

        # print(LT_x, LT_y, RB_x, RB_y)
        if LT_x > RB_x or LT_y > RB_y:
            QtWidgets.QMessageBox.warning(self, "警告", "右下角横纵坐标值均需大于左上角！",
                                          QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            return (-1,)*7
        return (LT_x,LT_y,RB_x,RB_y,Bad_Width,Bad_Height,Std_Height)

    # 定义设置响应函数
    def set_detect_roi(self):
        LT_x, LT_y, RB_x, RB_y, Bad_Width, Bad_Height, Std_Height = self.CheckSetInput()
        if -1 in (LT_x,LT_y,RB_x,RB_y,Bad_Width,Bad_Height,Std_Height):
            return

        # 主界面建立与所有前端的命令通信并传递到子界面
        try:
            data = struct.pack(self.parafmt, LT_x,LT_y,RB_x,RB_y,Bad_Width,Bad_Height,Std_Height)
            # print(struct.unpack(self.parafmt, data))  # 解包，查看是否打包正确
            self.server_cmd.send(data)
            data = struct.unpack(self.parafmt, self.server_cmd.recv(65536))
            # 之后进入监听状态，接收下位机返回，确定是否发送成功
            # 如果数据与设置不符，报错，转入except块执行
            print(data, type(data))
            if (LT_x,LT_y,RB_x,RB_y,Bad_Width,Bad_Height,Std_Height)==data:
                QtWidgets.QMessageBox.information(self,"提示","设置成功",QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No)
            else:
                raise socket.error

            # 设置成功后保存到config.cfg文件中并退出
            self.conf.set(self.machine, "LT_x", str(LT_x))
            self.conf.set(self.machine, "LT_y", str(LT_y))
            self.conf.set(self.machine, "RB_x", str(RB_x))
            self.conf.set(self.machine, "RB_y", str(RB_y))
            self.conf.set(self.machine, "Bad_Width", str(Bad_Width))
            self.conf.set(self.machine, "Bad_Height", str(Bad_Height))
            self.conf.set(self.machine, "Std_Height", str(Std_Height))
            self.conf.write(open('./config.cfg', 'w'))
        except:
            QtWidgets.QMessageBox.warning(self,
                                          "警告",
                                          "设置失败，请再次设置！",
                                          QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

    # 接收深度图像
    def recvdepthimage(self):
        addr = ('192.168.100.1', 20000)
        recvimg = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recvimg.bind(addr)
        recvimg.settimeout(2)
        try:
            with open('./depth.png', 'wb') as f:
                while 1:
                    data = recvimg.recv(16384)
                    if data != b'end':
                        f.write(data)
                    else:
                        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"), "recv depth image success")
                        break
            recvimg.close()
            return True
        except:
            recvimg.close()
            return False

    # 获取一帧图像---------
    def get1frame(self):
        self.server_cmd.settimeout(5)
        try:
            # self.server_cmd.setblocking(0)
            # self.server_cmd.settimeout(2)
            self.server_cmd.send(struct.pack('i', GET1FRAME))
            self.server_cmd.recv(65536)
            # data = struct.unpack(self.parafmt, self.server_cmd.recv(65536))
            # 接收深度图数据
            if self.recvdepthimage()==False:
                raise socket.error
            #time.sleep(1)
            self.depth = cv2.imread('./depth.png', cv2.IMREAD_UNCHANGED)
            depth = self.depth
            # self.get1frame_btn.setEnabled(False)
            # time.sleep(1)
            # self.get1frame_btn.setEnabled(True)
            global imgdecode
            i = self.index
            # 将彩色图像翻转后显示出来
            # self.image = imgdecode[i]
            # cv2.flip(self.image, 0, self.image)
            # cv2.flip(self.image, 1, self.image)
            # 将深度图转化成伪彩色显示出来
            self.image = cv2.applyColorMap(cv2.convertScaleAbs(depth, alpha=254/(depth.max()+1)), cv2.COLORMAP_JET)
            image = self.image.copy()
            imgsw = QImage(image.data, image.shape[1], image.shape[0], QImage.Format_RGB888)
            # imgsw = QImage(imgtest.data, imgtest.shape[1], imgtest.shape[0], QImage.Format_RGB888)
            self.label_imgsw.setScaledContents(True)  # 设置自适应大小，否则只显示部分
            self.label_imgsw.setPixmap(QPixmap.fromImage(imgsw))
            self.textEdit_information.setText("获取图像成功")
            self.pre_setting()
        except:
            # imgsw = QImage(imgtest.data, imgtest.shape[1], imgtest.shape[0], QImage.Format_RGB888)
            self.label_imgsw.setScaledContents(True)  # 设置自适应大小，否则只显示部分
            self.label_imgsw.setPixmap(QPixmap.fromImage(imageblack))
            self.textEdit_information.setText("网络故障，请检查后重新获取")
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"command error")

    def closeEvent(self, QCloseEvent):
        cv2.destroyAllWindows()

class Main_Form(QtWidgets.QWidget, Ui_Form):
    def __init__(self):
        super(Main_Form, self).__init__()
        self.setupUi(self)
        # 显示框对象名称
        self.LED = ['', self.label_door_name_1, self.label_door_name_2, self.label_door_name_3, self.label_door_name_4, self.label_door_name_5,
                    self.label_door_name_6, self.label_door_name_7, self.label_door_name_8, self.label_door_name_9, self.label_door_name_10,
                    self.label_door_name_11, self.label_door_name_12, self.label_door_name_13, self.label_door_name_14, self.label_door_name_15,
                    self.label_door_name_16, self.label_door_name_17, self.label_door_name_18, self.label_door_name_19, self.label_door_name_20,
                    self.label_door_name_21, self.label_door_name_22, self.label_door_name_23, self.label_door_name_24, self.label_door_name_25,
                    self.label_door_name_26, self.label_door_name_27, self.label_door_name_28, self.label_door_name_29, self.label_door_name_30,]
        # 连接函数名称
        self.OPENCAM = ['', self.connectnet, self.connectnet2, self.connectnet3, self.connectnet4, self.connectnet5,
                         self.connectnet6, self.connectnet7, self.connectnet8, self.connectnet9, self.connectnet10,
                         self.connectnet11, self.connectnet12, self.connectnet13, self.connectnet14, self.connectnet15,
                         self.connectnet16, self.connectnet17, self.connectnet18, self.connectnet19, self.connectnet20,
                         self.connectnet21, self.connectnet22, self.connectnet23, self.connectnet24, self.connectnet25,
                         self.connectnet26, self.connectnet27, self.connectnet28, self.connectnet29, self.connectnet30]
        # 获取配置参数：相机数量，检测异常时间（秒），串口号
        conf = configparser.ConfigParser()
        conf.read('./config.cfg')
        self.camNum = conf.getint("camera", "num")                  # 相机数
        self.CamConnnected = [0,]*31  # 0表示离线，1表示在线
        # 配置界面设置相机数
        for i in range(1, self.camNum+1):
            self.CamConnnected[i] = 1
        for i in range(self.camNum+1, 31):
            self.CamConnnected[i] = 0
            self.LED[i].setStyleSheet("background-color:rgb(0,255,0);")
        self.comboBox_index_sel.clear()
        for i in range(1,self.camNum+1):
            self.comboBox_index_sel.addItem(str(i))
        # 获取相机数量并显示
        self.INIT = True
        self.comboBox_Camnums.setCurrentIndex(self.camNum-1)

        self.isclear = [0,]*31  # 是否有异物标志位，用于自动停止检测的标志，如果有异物，那么再等5秒钟发送停止命令
        self.check_seconds = conf.getint("camera", "check_seconds") # 检测时间（秒）
        if self.check_seconds < 1:
            self.check_seconds = 5
        self.comno = conf.getint("camera", "com")                     # 串口号
        self.comboBox_ComID.setCurrentIndex(self.comno-1)

        # 获得可使用相机号，十进制数从1至30排列，每5个数一组，逗号隔开，
        # 比如4，5，6号相机可用时，表示为00001,11000,00000,00000,00000,00000
        str_using_cam = conf.get("camera", 'usingcam')
        using_cam = ''.join(str_using_cam.split(','))
        self.usingcam = []
        for j in using_cam:
            self.usingcam.append(j)

        #
        self.cnt = 0
        self.selIndex = -1  # 选中的窗口索引，-1表示未选中
        # 故障图片保存标志位，False表示该图片未保存，True表示已经保存
        # 初始和重置设为False，有问题并保存设为True
        self.ImageIsSaved = [False]*30
        # 故障图片显示标志位，False表示待显示，True表示已经显示
        # 初始和重置设为False，有问题并显示设为True
        self.ImageIsShowed = [False]*30
        # 图像显示框标志位, -1表示空闲
        # 若标志位与门序号相同或空则显示图像，否则不显示
        self.labelimg1 = -1
        self.labelimg2 = -1
        self.labelimg3 = -1
        # 图像接收IP
        self.addr_imgs = ['']  # ip:192.168.100.1, port=9901~9999
        for i in range(1, 40):
            # 暂用127.0.0.1测试-------
            # ip = '127.0.0.1'
            ip = '192.168.100.1'
            port = 9900+i
            self.addr_imgs.append((ip, port))

        self.label_imgsw.setPixmap(QPixmap.fromImage(imageblack))
        self.label_imgsw_2.setPixmap(QPixmap.fromImage(imageblack))
        self.label_imgsw_3.setPixmap(QPixmap.fromImage(imageblack))
        # 命令传送IP
        self.addr_cmds = ['']  # ip:192.168.100.101~199, port=10001~10099
        for i in range(1, 40):
            # 暂用127.0.0.1测试-------
            # ip = '127.0.0.1'
            ip = '192.168.100.'+str(100+i)
            port = 10000+i
            self.addr_cmds.append((ip, port))

        # 看门狗定时器，计时1秒，watchdogcnt计数，到5时并且没有异物就停止检测
        self.watchdog = QTimer()
        self.watchdog.timeout.connect(self.AutoStop)
        self.watchdogcnt = 0

        self.status = GET0FRAME
        # 初始化后即连接所有相机
        # 如果IP有问题，初始化后关闭界面
        self.IPCONN = True
        self.open_cam()
        if self.IPCONN == False:  # 如果未打开IP
            self.textEdit_information.insertPlainText("网线断开或IP地址设置错误，请检查后重启本软件！\n")
            # QtWidgets.QMessageBox.warning(self, "提示", "网线断开或IP地址设置错误，请检查后重启本软件！",
            #                               QtWidgets.QMessageBox.Ok)

        # 图像接收线程名称
        # self.RECTHREAD = ['', self.thread, self.thread2, self.thread3, self.thread4, self.thread5, self.thread6,
        #                   self.thread7, self.thread8, self.thread9, self.thread10, self.thread11, self.thread12,
        #                   self.thread13, self.thread14, self.thread15, self.thread16, self.thread17, self.thread18,
        #                   self.thread19, self.thread20, self.thread21, self.thread22, self.thread23, self.thread24,
        #                   self.thread25, self.thread26, self.thread27, self.thread28, self.thread29, self.thread30]
        # 开机自动进入复位状态
        # self.ChangeStatus(1)  # 将所有框置为蓝色
        self.isclear = [1, ] * 31
        #self.watchdog.stop()
        #self.get0frame()
        # self.textEdit_information.insertPlainText("工作中，已停止检查异物\n")
        # if self.tempFlag == True:
        #     self.textEdit_information.insertPlainText(com + "打开成功\n")
        # else:
        #     self.textEdit_information.insertPlainText(com + "打开失败\n")
        self.INIT = False
        print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"))

        # 打开指定串口
        com = "COM" + str(self.comno)
        try:
            self.comm = MSerialPort(com, 9600)
            self.t1 = threading.Thread(target = self.comm.read_data)
            self.t1.setDaemon(True)
            self.t1.start()
            self.comm.SerRecieved.connect(self.serrec)  # 接收信号与serrec函数连接
            self.tempFlag = True
            self.textEdit_information.insertPlainText("串口{}打开成功\n".format(self.comno))
        except:
            self.textEdit_information.insertPlainText("串口{}打开失败\n".format(self.comno))
            self.tempFlag = False
            print(r"串口{}打开失败\n".format(self.comno))


    def AutoStop(self):
        # 如果当前所有相机均为检测到异物，一直发送异物存在命令
        if 0 in self.isclear[1:]:
            self.comm.send_data(SERCMD_BAD)
        else:
            self.comm.send_data(SERCMD_OK)
            self.watchdogcnt = (self.watchdogcnt+1)%self.check_seconds
            if self.watchdogcnt == 0:  # 计数到5并且没有异物
                self.get0frame()  # 发送停止检测命令
                self.watchdog.stop()
                self.ChangeStatus(1)
                self.textEdit_information.insertPlainText("工作中，已停止检查异物\n")

    def UpdateCamNum(self):
        if self.INIT:
            return
        self.camNum = int(self.comboBox_Camnums.currentText())
        conf = configparser.ConfigParser()
        conf.read('./config.cfg')
        conf.set("camera","num",str(self.camNum))
        conf.write(open("./config.cfg", 'w'))
        # print(self.camNum)
        # 配置界面设置相机数，原本为0的设为1
        for i in range(1, self.camNum+1):
            if self.CamConnnected[i] == 0:
                self.CamConnnected[i] = 1
        for i in range(self.camNum+1, 31):
            self.CamConnnected[i] = 0
            self.LED[i].setStyleSheet("background-color:rgb(0,255,0);")
        self.comboBox_index_sel.clear()
        for i in range(1,self.camNum+1):
            self.comboBox_index_sel.addItem(str(i))

    def UpdateComID(self):
        if self.INIT:
            return
        self.comno = int(self.comboBox_ComID.currentText())
        conf = configparser.ConfigParser()
        conf.read('./config.cfg')
        conf.set("camera", "com", str(self.comno))
        conf.write(open("./config.cfg", 'w'))
        self.textEdit_information.insertPlainText("已经修改串口号，请退出软件后重新打开\n")
        return
        # 修改串口后，需要重新打开软件
        # com = 'COM{}'.format(self.comno)
        # try:
        #     self.comm = MSerialPort(com, 9600)
        #     self.t1 = threading.Thread(target=self.comm.read_data)
        #     self.t1.start()
        #     self.comm.SerRecieved.connect(self.serrec)  # 接收信号与serrec函数连接
        #     self.tempFlag = True
        #     self.textEdit_information.insertPlainText("串口{}打开成功\n".format(self.comno))
        # except:
        #     self.textEdit_information.insertPlainText("串口{}打开失败\n".format(self.comno))
        #     self.tempFlag = False
        #     print(r"串口{}打开失败\n".format(self.comno))

    def ChangeStatus(self, color):  # 1表示蓝色， 2表示灰色，3表示黄色
        gray = "background-color:rgb({0},{0},{0});".format(127)
        blue = "background-color:rgb(0,0,{0});".format(255)
        yellow = "background-color:rgb({0},{0},0);".format(255)
        if color == 1:
            bk = blue
        elif color == 2:
            bk = gray
        elif color == 3:
            bk = yellow
        else:
            bk = blue
        self.label_door_1.setStyleSheet(bk)
        self.label_door_2.setStyleSheet(bk)
        self.label_door_3.setStyleSheet(bk)
        self.label_door_4.setStyleSheet(bk)
        self.label_door_5.setStyleSheet(bk)
        self.label_door_6.setStyleSheet(bk)
        self.label_door_7.setStyleSheet(bk)
        self.label_door_8.setStyleSheet(bk)
        self.label_door_9.setStyleSheet(bk)
        self.label_door_10.setStyleSheet(bk)
        self.label_door_11.setStyleSheet(bk)
        self.label_door_12.setStyleSheet(bk)
        self.label_door_13.setStyleSheet(bk)
        self.label_door_14.setStyleSheet(bk)
        self.label_door_15.setStyleSheet(bk)
        self.label_door_16.setStyleSheet(bk)
        self.label_door_17.setStyleSheet(bk)
        self.label_door_18.setStyleSheet(bk)
        self.label_door_19.setStyleSheet(bk)
        self.label_door_20.setStyleSheet(bk)
        self.label_door_21.setStyleSheet(bk)
        self.label_door_22.setStyleSheet(bk)
        self.label_door_23.setStyleSheet(bk)
        self.label_door_24.setStyleSheet(bk)
        self.label_door_25.setStyleSheet(bk)
        self.label_door_26.setStyleSheet(bk)
        self.label_door_27.setStyleSheet(bk)
        self.label_door_28.setStyleSheet(bk)
        self.label_door_29.setStyleSheet(bk)
        self.label_door_30.setStyleSheet(bk)

    def serrec(self):
        # if self.ser.recv_data == SERCMD_OPEN:  # 正常状态(停止检测)，全部显示蓝色
        #     self.ChangeStatus(1)  # 将所有框置为蓝色
        #     self.isclear=[1,]*31
        #     self.watchdog.stop()
        #     self.get0frame()
        if self.comm.recv_data == SERCMD_CLOS:  # 上下行人状态（停止检测），显示灰色
            self.ChangeStatus(2)  # 将所有框置为灰色
            self.get0frame()
            self.textEdit_information.insertPlainText("开门中，已停止检查异物\n")
        if self.comm.recv_data == SERCMD_DETE:  # 检测状态（正在检测），显示黄色？
            self.ChangeStatus(3)
            self.getMframe()  # 发送开始工作命令，检测5秒钟后停止
            self.watchdog.start(1000)
            self.textEdit_information.insertPlainText("正在检查异物...\n")
        if self.comm.recv_data == SERCMD_6: # 复位状态，停止检测，清除报警，显示蓝色，与正常状态的区别是该状态由IO盒的按钮按下发出
            self.ChangeStatus(1)  # 将所有框置为蓝色
            self.isclear = [1, ] * 31
            self.watchdog.stop()
            self.get0frame()
            self.textEdit_information.insertPlainText("工作中，已停止检查异物\n")
        # print(self.comm.recv_data)

    # 连接按钮，连接所有相机用
    def open_cam(self):
        # self.UpdateCamNum()
        # print(self.CamConnnected)
        num = 0
        if self.INIT:
            num = 31
        else:
            num = self.camNum+1
        self.textEdit_information.setText('')
        for i in range(1, num):
            if self.usingcam[i-1]=='1':
                self.OPENCAM[i]()
    # 暂停按钮
    def get0frame(self):
        # self.UpdateCamNum()
        self.status = GET0FRAME
        self.textEdit_information.setText('')
        for i, addr in enumerate(self.addr_cmds[1:self.camNum+1]):
            if self.CamConnnected[i+1] == 2:  # 相机启动但是未在线
                self.textEdit_information.insertPlainText("{}号前端未连接\n".format(i+1))
                continue
            server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            server.connect(addr)
            server.settimeout(0.1)
            try:
                server.send(struct.pack('i', GET0FRAME))
                # print(addr, type(addr))
                data = struct.unpack(parameterfmt, server.recv(65536))
                if data[0] == GET0FRAME:
                    info = "{}号前端暂停工作！".format(i + 1)
                else:
                    info = "{}号前端暂停失败！".format(i + 1)
            except:
                info = "{}号前端暂停错误！".format(i + 1)
            # self.textEdit_information.insertPlainText(info)
            print(info)
            server.close()

    # 开始工作
    def getMframe(self):
        # self.UpdateCamNum()
        self.status = GETMFRAME
        self.textEdit_information.setText('')
        for i, addr in enumerate(self.addr_cmds[1:self.camNum+1]):
            if self.CamConnnected[i+1] == 2:  # 相机启动但是未在线
                self.textEdit_information.insertPlainText("{}号前端未连接\n".format(i+1))
                continue
            server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            server.connect(addr)
            server.settimeout(0.1)
            try:
                # server.setblocking(0)
                server.sendall(struct.pack('i', GETMFRAME))
                # server.send(struct.pack('i', 4)) # 发送测试代码
                # print(addr, type(addr))
                data = struct.unpack(parameterfmt, server.recv(65536))
                # print(data, type(data))
                if data[0] == GETMFRAME:
                    info = "{}号前端开始工作！".format(i + 1)
                else:
                    info = "{}号前端工作失败！".format(i + 1)
            except:
                info = "{}号前端工作错误！".format(i + 1)
            server.close()
            # self.textEdit_information.insertPlainText(info)
            print(info)

    def testfunc(self):
        try:
            if self.ser.ser.isOpen():
                self.ser.send_data(SERCMD_OPEN)
            else:
                print("串口被占用")
        except:
            print("串口未打开")

    def Imgswtest(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        if isClear == -1:
            self.textEdit_info.setText("OK")
        elif isClear == 1:
            cv2.rectangle(imgdecode[1], (0,0), (imgdecode[1].shape[1], imgdecode[1].shape[0]), (0, 0, 255), 3)
            self.textEdit_info.setText("Warning!!!")
        # 转换成QLabel可以显示的格式
        cv2.cvtColor(imgdecode[1], cv2.COLOR_BGR2RGB, imgdecode[1])
        imgsw = QImage(imgdecode[1].data, imgdecode[1].shape[1], imgdecode[1].shape[0], QImage.Format_RGB888)
        # imgsw = QImage(imgtest.data, imgtest.shape[1], imgtest.shape[0], QImage.Format_RGB888)
        self.label_imgsw.setScaledContents(True)  # 设置自适应大小，否则只显示部分
        self.label_imgsw.setPixmap(QPixmap.fromImage(imgsw))

    # set_detect_roi响应函数
    def slotcalldlg(self):
        # self.textEdit_information.setText("open a new subdlg")
        # 模态对话框
        status = self.status
        self.status = SETTINGRE
        global imgdecode
        index = int(self.comboBox_index_sel.currentText())
        if self.CamConnnected[index] == 2:  # 2表示已启用但未在线
            QtWidgets.QMessageBox.warning(self,
                                          "警告",
                                          "{}号前端未连接，不能进行设置！".format(index),
                                          QtWidgets.QMessageBox.Ok)
            return
        addr = self.addr_cmds[index]
        newDialog = SetDlg(image=imgdecode[index], index=index, addr=addr)  # 打开设置对话框(模态)，传入图像和序号参数
        newDialog.exec_()
        self.status = status
        # 如果设置前是工作状态，设置后也是工作状态
        if self.status == GETMFRAME:
            self.getMframe()
        # self.textEdit_information.setText("close a dlg")

    # 连接状态显示函数
    def ChangeConStatus(self, index, isClear):
        if self.CamConnnected[index]==0:  # 相机不启用
            # 显示绿色
            self.LED[index].setStyleSheet("background-color:rgb(0,255,0);")
        if self.CamConnnected[index]==1 and isClear==CAMOFLINE:  # 相机启用，但未接收到任何信号，即掉线
            # 显示红色并且将相机状态置为2，表示启动但掉线
            self.LED[index].setStyleSheet("background-color:rgb(255,0,0);")
            self.CamConnnected[index] = 2
        if self.CamConnnected[index]==2 and isClear!=CAMOFLINE:  # 相机启用，并接收到信号
            # 显示绿色并将相机状态置为1，表示启用并在线
            self.LED[index].setStyleSheet("background-color:rgb(0,255,0);")
            self.CamConnnected[index] = 1

    # 实现connectnet函数，textEdit是我们放上去的文本框的id
    # btn响应函数
    def connectnet(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[1]
        # print(addr)
        self.thread = RecImgThread(addr=addr, index=1)
        if self.thread.working == False:  # 没有打开
            self.IPCONN = False
            # self.close()
            # self.closeEvent(QtGui.QCloseEvent)
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(1, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread.isClear.connect(self.Imgsw)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 1
        self.isclear[index] = isClear
        if isClear == 1:
            #self.textEdit_info.setText("OK")
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_1.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(1)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_1.setStyleSheet("background-color:rgb(255,0,0);")
            # cv2.rectangle(imgdecode[1], (0,0), (imgdecode[1].shape[1], imgdecode[1].shape[0]), (255, 0, 0), 3)
            # self.textEdit_info.setText("Warning!!!")
            # 显示该位置图像
            self.ShowImg(1)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(1))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    # 打开第2个线程
    def connectnet2(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[2]
        self.thread2 = RecImgThread(addr, index=2)
        if self.thread2.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(2, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread2.isClear.connect(self.Imgsw2)
            self.thread2.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

        # slot函数，接收线程信号，显示图像在控件label_imgsw_2框中
    def Imgsw2(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 2
        self.isclear[index] = isClear
        if isClear == 1:
            # self.textEdit_info.setText("OK")
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_2.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(2)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_2.setStyleSheet("background-color:rgb(255,0,0);")
            # cv2.rectangle(imgdecode[1], (0,0), (imgdecode[1].shape[1], imgdecode[1].shape[0]), (255, 0, 0), 3)
            # self.textEdit_info.setText("Warning!!!")
            # 显示该位置图像
            self.ShowImg(2)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(2))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    # 实现connectnet函数，textEdit是我们放上去的文本框的id
    # btn响应函数
    def connectnet3(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[3]
        self.thread3 = RecImgThread(addr=addr, index=3)
        if self.thread3.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(3, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread3.isClear.connect(self.Imgsw3)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread3.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw3(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 3
        self.isclear[index] = isClear
        if isClear == 1:
            # self.textEdit_info.setText("OK")
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_3.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(3)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_3.setStyleSheet("background-color:rgb(255,0,0);")
            # cv2.rectangle(imgdecode[1], (0,0), (imgdecode[1].shape[1], imgdecode[1].shape[0]), (255, 0, 0), 3)
            # self.textEdit_info.setText("Warning!!!")
            # 显示该位置图像
            self.ShowImg(3)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(3))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet4(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[4]
        self.thread4 = RecImgThread(addr=addr, index=4)
        if self.thread4.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(4, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread4.isClear.connect(self.Imgsw4)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread4.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw4(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 4
        self.isclear[index] = isClear
        if isClear == 1:
            # self.textEdit_info.setText("OK")
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_4.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(4)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_4.setStyleSheet("background-color:rgb(255,0,0);")
            # cv2.rectangle(imgdecode[1], (0,0), (imgdecode[1].shape[1], imgdecode[1].shape[0]), (255, 0, 0), 3)
            # self.textEdit_info.setText("Warning!!!")
            # 显示该位置图像
            self.ShowImg(4)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(4))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet5(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[5]
        self.thread5 = RecImgThread(addr=addr, index=5)
        if self.thread5.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(5, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread5.isClear.connect(self.Imgsw5)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread5.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw5(self, isClear):
        global imgdecode  # 声明使用的全局变量
        ## test code
        # for i in [1,3,4,5]:
        #     cv2.imshow("{}号相机".format(i), imgdecode[i])
        #     cv2.waitKey(1)
        # 如果没有异物
        index = 5
        self.isclear[index] = isClear
        if isClear == 1:
            # self.textEdit_info.setText("OK")
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_5.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(5)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_5.setStyleSheet("background-color:rgb(255,0,0);")
            # cv2.rectangle(imgdecode[1], (0,0), (imgdecode[1].shape[1], imgdecode[1].shape[0]), (255, 0, 0), 3)
            # self.textEdit_info.setText("Warning!!!")
            # 显示该位置图像
            self.ShowImg(5)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(5))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet6(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[6]
        self.thread6 = RecImgThread(addr=addr, index=6)
        if self.thread6.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(6, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread6.isClear.connect(self.Imgsw6)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread6.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw6(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 6
        self.isclear[index] = isClear
        if isClear == 1:
            # self.textEdit_info.setText("OK")
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_6.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(6)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_6.setStyleSheet("background-color:rgb(255,0,0);")
            # cv2.rectangle(imgdecode[1], (0,0), (imgdecode[1].shape[1], imgdecode[1].shape[0]), (255, 0, 0), 3)
            # self.textEdit_info.setText("Warning!!!")
            # 显示该位置图像
            self.ShowImg(6)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(6))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet7(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[7]
        self.thread7 = RecImgThread(addr=addr, index=7)
        if self.thread7.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(7, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread7.isClear.connect(self.Imgsw7)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread7.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw7(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 7
        self.isclear[index] = isClear
        if isClear == 1:
            # self.textEdit_info.setText("OK")
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_7.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(7)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_7.setStyleSheet("background-color:rgb(255,0,0);")
            # cv2.rectangle(imgdecode[1], (0,0), (imgdecode[1].shape[1], imgdecode[1].shape[0]), (255, 0, 0), 3)
            # self.textEdit_info.setText("Warning!!!")
            # 显示该位置图像
            self.ShowImg(7)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(7))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet8(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[8]
        self.thread8 = RecImgThread(addr=addr, index=8)
        if self.thread8.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(8, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread8.isClear.connect(self.Imgsw8)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread8.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw8(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 8
        self.isclear[index] = isClear
        if isClear == 1:
            # self.textEdit_info.setText("OK")
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_8.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(8)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_8.setStyleSheet("background-color:rgb(255,0,0);")
            # cv2.rectangle(imgdecode[1], (0,0), (imgdecode[1].shape[1], imgdecode[1].shape[0]), (255, 0, 0), 3)
            # self.textEdit_info.setText("Warning!!!")
            # 显示该位置图像
            self.ShowImg(8)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(8))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet9(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[9]
        self.thread9 = RecImgThread(addr=addr, index=9)
        if self.thread9.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(9, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread9.isClear.connect(self.Imgsw9)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread9.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw9(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 9
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_9.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(9)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_9.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(9)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(9))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet10(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[10]
        self.thread10 = RecImgThread(addr=addr, index=10)
        if self.thread10.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(10, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread10.isClear.connect(self.Imgsw10)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread10.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw10(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 10
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_10.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(10)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_10.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(10)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(10))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet11(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[11]
        self.thread11 = RecImgThread(addr=addr, index=11)
        if self.thread11.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(11, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread11.isClear.connect(self.Imgsw11)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread11.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw11(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 11
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_11.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(11)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_11.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(11)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(11))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet12(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[12]
        self.thread12 = RecImgThread(addr=addr, index=12)
        if self.thread12.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(12, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread12.isClear.connect(self.Imgsw12)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread12.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw12(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 12
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_12.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(12)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_12.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(12)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(12))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet13(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[13]
        self.thread13 = RecImgThread(addr=addr, index=13)
        if self.thread13.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(13, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread13.isClear.connect(self.Imgsw13)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread13.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw13(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 13
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_13.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(13)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_13.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(13)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(13))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet14(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[14]
        self.thread14 = RecImgThread(addr=addr, index=14)
        if self.thread14.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(14, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread14.isClear.connect(self.Imgsw14)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread14.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw14(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 14
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_14.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(14)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_14.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(14)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(14))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet15(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[15]
        self.thread15 = RecImgThread(addr=addr, index=15)
        if self.thread15.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(15, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread15.isClear.connect(self.Imgsw15)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread15.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw15(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 15
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_15.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(15)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_15.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(15)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(15))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet16(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[16]
        self.thread16 = RecImgThread(addr=addr, index=16)
        if self.thread16.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(16, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread16.isClear.connect(self.Imgsw16)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread16.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw16(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 16
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_16.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(16)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_16.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(16)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(16))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet17(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[17]
        self.thread17 = RecImgThread(addr=addr, index=17)
        if self.thread17.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(17, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread17.isClear.connect(self.Imgsw17)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread17.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw17(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 17
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_17.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(17)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_17.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(17)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(17))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet18(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[18]
        self.thread18 = RecImgThread(addr=addr, index=18)
        if self.thread18.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(18, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread18.isClear.connect(self.Imgsw18)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread18.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw18(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 18
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_18.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(18)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_18.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(18)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(18))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet19(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[19]
        self.thread19 = RecImgThread(addr=addr, index=19)
        if self.thread19.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(19, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread19.isClear.connect(self.Imgsw19)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread19.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw19(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 19
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_19.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(19)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_19.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(19)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(19))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet20(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[20]
        self.thread20 = RecImgThread(addr=addr, index=20)
        if self.thread20.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(20, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread20.isClear.connect(self.Imgsw20)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread20.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw20(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 20
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_20.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(20)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_20.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(20)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(20))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet21(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[21]
        self.thread21 = RecImgThread(addr=addr, index=21)
        if self.thread21.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(21, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread21.isClear.connect(self.Imgsw21)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread21.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw21(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 21
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_21.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(21)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_21.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(21)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(21))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet22(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[22]
        self.thread22 = RecImgThread(addr=addr, index=22)
        if self.thread22.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(22, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread22.isClear.connect(self.Imgsw22)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread22.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw22(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 22
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_22.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(22)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_22.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(22)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(22))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet23(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[23]
        self.thread23 = RecImgThread(addr=addr, index=23)
        if self.thread23.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(23, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread23.isClear.connect(self.Imgsw23)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread23.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw23(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 23
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_23.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(23)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_23.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(23)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(23))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet24(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[24]
        self.thread24 = RecImgThread(addr=addr, index=24)
        if self.thread24.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(24, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread24.isClear.connect(self.Imgsw24)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread24.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw24(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 24
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_24.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(24)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_24.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(24)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(24))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet25(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[25]
        self.thread25 = RecImgThread(addr=addr, index=25)
        if self.thread25.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(25, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread25.isClear.connect(self.Imgsw25)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread25.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw25(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 25
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_25.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(25)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_25.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(25)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(25))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet26(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[26]
        self.thread26 = RecImgThread(addr=addr, index=26)
        if self.thread26.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(26, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread26.isClear.connect(self.Imgsw26)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread26.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw26(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 26
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_26.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(26)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_26.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(26)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(26))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet27(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[27]
        self.thread27 = RecImgThread(addr=addr, index=27)
        if self.thread27.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(27, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread27.isClear.connect(self.Imgsw27)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread27.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw27(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 27
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_27.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(27)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_27.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(27)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(27))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet28(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[28]
        self.thread28 = RecImgThread(addr=addr, index=28)
        if self.thread28.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(28, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread28.isClear.connect(self.Imgsw28)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread28.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw28(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 28
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_28.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(28)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_28.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(28)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(28))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet29(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[29]
        self.thread29 = RecImgThread(addr=addr, index=29)
        if self.thread29.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(29, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread29.isClear.connect(self.Imgsw29)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread29.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw29(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 29
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_29.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(29)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_29.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(29)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(29))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    def connectnet30(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[30]
        self.thread30 = RecImgThread(addr=addr, index=30)
        if self.thread30.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开{}前端失败\n".format(addr[1]-9900))
            self.ChangeConStatus(30, CAMOFLINE)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread30.isClear.connect(self.Imgsw30)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread30.start()
            # 显示线程信息
            info = "打开{}前端成功".format(addr[1]-9900)
            # self.textEdit_information.insertPlainText(info)
            print(info)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw30(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
        index = 30
        self.isclear[index] = isClear
        if isClear == 1:
            # 设置门为蓝色（后期改成蓝色门图像）
            self.label_door_30.setStyleSheet("background-color:rgb(0,0,255);")
            self.ChangeLabelFlag(30)
        elif isClear == 0:  # 如果有异物
            # 设置门为红色（后期改成红色门图像）
            self.label_door_30.setStyleSheet("background-color:rgb(255,0,0);")
            # 显示该位置图像
            self.ShowImg(30)
        elif isClear == CAMERROR:  # 如果收到摄像头错误
            print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S:"),"{}号前端相机未连接，请检查线路后重启".format(30))
        # 新增检测下位机状态代码
        # 如果未检测到握手信息并且相机在使用范围内，则显示掉线
        self.ChangeConStatus(index, isClear)

    # 轮询图像显示框，若为空闲则显示指定门序号的图像
    # 查询图像是否保存，未保存则保存
    def ShowImg(self, doorID):
        image = imgdecode[doorID].copy()
        cv2.flip(image,0,image)
        cv2.flip(image,1,image)
        imgsw = QImage(image.data, image.shape[1], image.shape[0], QImage.Format_RGB888)
        # imgsw = QImage(imgtest.data, imgtest.shape[1], imgtest.shape[0], QImage.Format_RGB888)
        # 查看故障图像是否保存，未保存则保存图像
        if self.ImageIsSaved[doorID-1] == False:  # False表示没有保存
            cur = datetime.datetime.now()
            imagename = "./images/{}号门故障{}年{}月{}日{}时{}分{}秒.jpg".format(doorID, cur.year, cur.month, cur.day,
                                                                       cur.hour, cur.minute, cur.second)
            imgsw.save(imagename, 'JPG', -1)
            self.ImageIsSaved[doorID-1] = True  # True表示已经保存
        # # 如果没有空闲显示框，则返回
        # if not (-1 in [self.labelimg1,self.labelimg2,self.labelimg3]):
        #     return
        # 查询图像显示框是否可用，若可用即显示
        if(self.labelimg1==self.labelimg2 and self.labelimg1 != -1):
            self.labelimg2=-1
            self.textEdit_info_2.setText("")
            self.label_imgsw_2.setPixmap(QPixmap.fromImage(imageblack))
        if(self.labelimg1==self.labelimg3 and self.labelimg1 != -1):
            self.labelimg3=-1
            self.textEdit_info_3.setText("")
            self.label_imgsw_3.setPixmap(QPixmap.fromImage(imageblack))
        if(self.labelimg2==self.labelimg3 and self.labelimg2 != -1):
            self.labelimg3=-1
            self.textEdit_info_3.setText("")
            self.label_imgsw_3.setPixmap(QPixmap.fromImage(imageblack))
        if ((self.labelimg1==-1)==self.ImageIsShowed[doorID-1]) or ((self.labelimg1==doorID)==self.ImageIsShowed[doorID-1]):
            self.textEdit_info.setText("{}号门有异物！！！".format(doorID))
            self.label_imgsw.setScaledContents(True)  # 设置自适应大小，否则只显示部分
            self.label_imgsw.setPixmap(QPixmap.fromImage(imgsw))
            self.labelimg1=doorID
            self.ImageIsShowed[doorID-1]=True
            return
        if ((self.labelimg2==-1)==self.ImageIsShowed[doorID-1]) or ((self.labelimg2==doorID)==self.ImageIsShowed[doorID-1]):
            self.textEdit_info_2.setText("{}号门有异物！！！".format(doorID))
            self.label_imgsw_2.setScaledContents(True)  # 设置自适应大小，否则只显示部分
            self.label_imgsw_2.setPixmap(QPixmap.fromImage(imgsw))
            self.labelimg2=doorID
            self.ImageIsShowed[doorID-1]=True
            return
        if ((self.labelimg3==-1)==self.ImageIsShowed[doorID-1]) or ((self.labelimg3==doorID)==self.ImageIsShowed[doorID-1]):
            self.textEdit_info_3.setText("{}号门有异物！！！".format(doorID))
            self.label_imgsw_3.setScaledContents(True)  # 设置自适应大小，否则只显示部分
            self.label_imgsw_3.setPixmap(QPixmap.fromImage(imgsw))
            self.labelimg3=doorID
            self.ImageIsShowed[doorID-1]=True
            return

    # 重置图像显示标志位和显示框, 在门内无异物时调用此函数
    def ChangeLabelFlag(self, doorID):
        # 重置标志位
        global imageblack
        self.ImageIsShowed[doorID-1] = False
        self.ImageIsSaved[doorID-1] = False
        if self.labelimg1==doorID:
            self.textEdit_info.setText("")
            self.labelimg1=-1
            self.label_imgsw.setPixmap(QPixmap.fromImage(imageblack))
            return
        if self.labelimg2==doorID:
            self.textEdit_info_2.setText("")
            self.labelimg2=-1
            self.label_imgsw_2.setPixmap(QPixmap.fromImage(imageblack))
            return
        if self.labelimg3==doorID:
            self.textEdit_info_3.setText("")
            self.label_imgsw_3.setPixmap(QPixmap.fromImage(imageblack))
            self.labelimg3=-1
            return

    # 关闭提醒
    def closeEvent(self, QCloseEvent):
        if True:#if self.IPCONN == True:
            relpy = QtWidgets.QMessageBox.question(self, "提示", "确认关闭？", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if relpy == QtWidgets.QMessageBox.Yes:
                self.comm.state = False
                if self.comm.isOpen()
                    self.comm.port_close()
                self.watchdog.stop()
                # self.t1.stop()
                QCloseEvent.accept()
            else:
                QCloseEvent.ignore()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main_form = Main_Form()
    with open("interface.qss") as f:
        qss = f.read()
    app.setStyleSheet(qss)
    main_form.show()
    sys.exit(app.exec_())
