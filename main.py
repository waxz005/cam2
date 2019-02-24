# -*- coding: utf-8 -*-
# 主文件，实现主界面的函数

import sys, os
from PyQt5 import QtWidgets, QtCore, QtGui
from MainWindow import Ui_Form
from setroidlg import Ui_Dlg_setroi
from PyQt5.QtCore import QThread, QEvent
from PyQt5.QtGui import QImage, QPixmap
import cv2
import numpy as np
import socket
import struct
import datetime
import configparser
import time

GET0FRAME = 0
GET1FRAME = 2
GETMFRAME = 1
CAMERROR = 5
parameterfmt = 'iiiiiii'

# 测试用数据
HOST = '127.0.0.1'
PORT = 9999
buffSize = 65535
cnt = 0
global imgtest

imageblack = np.zeros((480, 640), np.uint8)
imageblack = QImage(imageblack.data, imageblack.shape[1], imageblack.shape[0], QImage.Format_Grayscale8)
# 测试用数据结束
# 图像全局变量，socket接收到数据后存入其中，并发送signal
# 预置了30个640*480*3大小的u8类型图像文件，后续需要还可以继续扩充
imgdecode = [np.zeros((480, 640, 3), np.uint8)] * 31

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
            self.working = True
        except:
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
            # if not self.working: return
            # 第一次接收到的数据，根据协议，为数据长度
            data, address = self.server.recvfrom(self.buffsize)
            # 测试用协议，现已无用
            if len(data) == 2 and data == b'ok':
                self.isClear.emit(-1)
            if len(data) == 1 and data[0] == 1:  # 如果收到关闭消息则停止程序
                self.server.close()
                # cv2.destroyAllWindows()
            # 测试用协议，现已无用
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
                print('one frame is lost!!!')
                self.num += 1    # 暂时没想好干什么用
                print(self.num)  # 暂时用于统计掉帧个数，但不完整，因为length和isClear也有掉帧，并未统计在内
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
            if event.type() == QEvent.MouseButtonDblClick:
                self.textEdit_information.setText("双击了Label")
            elif event.type() == QEvent.MouseButtonPress:
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
        try:
            # -1避免溢出
            LT_x = int(self.lineEdit_LT_x.text())
            LT_y = int(self.lineEdit_LT_y.text())
            RB_x = int(self.lineEdit_RB_x.text())-1
            RB_y = int(self.lineEdit_RB_y.text())-1
            Bad_Width = int(self.lineEdit_badWidth.text())
            Bad_Height = int(self.lineEdit_badHeight.text())
            Std_Height = int(self.lineEdit_stdHeight.text())
        except:
            QtWidgets.QMessageBox.warning(self,"警告","坐标值不能为空！",QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            return

        # print(LT_x, LT_y, RB_x, RB_y)
        if LT_x > RB_x or LT_y > RB_y:
            QtWidgets.QMessageBox.warning(self,"警告","右下角横纵坐标值均需大于左上角！",QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            return

        # 测试代码
        # 测试代码

        # 画出区域
        image = self.image.copy()
        roi = self.depth[LT_y:RB_y,LT_x:RB_x].copy()
        roimax = roi.max()
        roimin = roi.min()
        roimean = roi.mean()
        cv2.convertScaleAbs(roi,roi,255./roimax)
        cv2.blur(roi,(15,15),roi)
        #cv2.threshold(roi,(Std_Height-Bad_Height*0.7)*255/roimax,1,cv2.THRESH_BINARY_INV,roi)
        # refcnt = np.sum(roi)
        refcnt = np.sum((roi<Std_Height-Bad_Height))
        refcnt = int(np.sqrt(refcnt+660))
        self.textEdit_information.setText("区域最远:{} 区域最近:{} 区域均值:{} 参考值:{}".format(roimax, roimin,int(roimean),refcnt))
        # cv2.imshow('1', image[LT_y:RB_y,LT_x:RB_x]);cv2.waitKey(0)
        # 画矩形
        cv2.rectangle(image, (LT_x, LT_y), (RB_x, RB_y), (50, 200, 127), 3)
        # 减少固定值
        num = np.zeros(image[LT_y:RB_y, LT_x:RB_x].shape, image.dtype) + 50
        image[LT_y:RB_y, LT_x:RB_x] = cv2.subtract(image[LT_y:RB_y, LT_x:RB_x], num)
        #image[LT_x:RB_x, LT_y:RB_y] = cv2.addWeighted(image[LT_x:RB_x, LT_y:RB_y], 0.5, [255, 255, 255], 0.5)

        imgsw = QImage(image.data, image.shape[1], image.shape[0], QImage.Format_RGB888)
        self.label_imgsw.setPixmap(QPixmap.fromImage(imgsw))

    # 定义设置响应函数
    def set_detect_roi(self):
        # 检查输入是否有问题，尚不完备
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
            QtWidgets.QMessageBox.warning(self,"警告","坐标值不能为空！",QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            return

        # print(LT_x, LT_y, RB_x, RB_y)
        if LT_x > RB_x or LT_y > RB_y:
            QtWidgets.QMessageBox.warning(self,"警告","右下角横纵坐标值均需大于左上角！",QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
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

    # 获取一帧图像---------
    def get1frame(self):
        try:
            # self.server_cmd.setblocking(0)
            self.server_cmd.settimeout(2)
            self.server_cmd.send(struct.pack('i', GET1FRAME))
            self.server_cmd.recv(65536)
            # data = struct.unpack(self.parafmt, self.server_cmd.recv(65536))
            # 接收深度图数据
            f = open('./depth.png', 'wb')
            while 1:
                data, addr = self.server_cmd.recvfrom(1024)
                if data != b'end':
                    f.write(data)
                else:
                    print("recv depth image success")
                    break
            f.close()
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
        except:
            # imgsw = QImage(imgtest.data, imgtest.shape[1], imgtest.shape[0], QImage.Format_RGB888)
            self.label_imgsw.setScaledContents(True)  # 设置自适应大小，否则只显示部分
            self.label_imgsw.setPixmap(QPixmap.fromImage(imageblack))
            self.textEdit_information.setText("获取图像失败，请重新获取")
            print("command error")

class Main_Form(QtWidgets.QWidget, Ui_Form):
    def __init__(self):
        super(Main_Form, self).__init__()
        self.setupUi(self)
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

        # 测试用数据
        # self.addr_imgs[1]=('192.168.1.3',9901)
        # self.addr_imgs[2]=('127.0.0.1',9902)
        # self.addr_cmds[1]=('192.168.1.16', 10001)
        # self.addr_cmds[2]=('127.0.0.1',10002)

    # 连接按钮，连接所有相机用
    def open_cam(self):
        self.textEdit_information.setText('')
        self.connectnet()
        self.connectnet2()
        self.connectnet3()
        self.connectnet4()
        self.connectnet5()

    # 暂停按钮
    def get0frame(self):
        self.textEdit_information.setText('')
        for i, addr in enumerate(self.addr_cmds[1:]):
            server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            server.connect(addr)
            server.settimeout(0.1)
            try:
                server.send(struct.pack('i', GET0FRAME))
                # print(addr, type(addr))
                data = struct.unpack(parameterfmt, server.recv(65536))
                if data[0] == GET0FRAME:
                    info = "{}号前端暂停成功！\n".format(i + 1)
                else:
                    info = "{}号前端暂停失败！\n".format(i + 1)
            except:
                info = "{}号前端暂停错误！\n".format(i + 1)
            self.textEdit_information.insertPlainText(info)
            server.close()

    # 开始工作
    def getMframe(self):
        self.textEdit_information.setText('')
        for i, addr in enumerate(self.addr_cmds[1:]):
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
                    info = "{}号前端打开成功！\n".format(i + 1)
                else:
                    info = "{}号前端打开失败！\n".format(i + 1)
            except:
                info = "{}号前端打开错误！\n".format(i + 1)
            server.close()
            self.textEdit_information.insertPlainText(info)

    def testfunc(self):
        self.label_door_1.setStyleSheet("background-color:rgb(255,0,0);")  # 设置背景颜色为RGB

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
        self.textEdit_information.setText("open a new subdlg")
        # 模态对话框
        global imgdecode
        index = int(self.comboBox_index_sel.currentText())
        addr = self.addr_cmds[index]
        newDialog = SetDlg(image=imgdecode[index], index=index, addr=addr)  # 打开设置对话框(模态)，传入图像和序号参数
        newDialog.exec_()
        self.textEdit_information.setText("close a dlg")

    # 实现connectnet函数，textEdit是我们放上去的文本框的id
    # btn响应函数
    def connectnet(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[1]
        # print(addr)
        self.thread = RecImgThread(addr=addr, index=1)
        if self.thread.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开IP：{}，端口：{} 失败\n".format(addr[0], addr[1]))
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread.isClear.connect(self.Imgsw)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread.start()
            # 显示线程信息
            info = "打开了地址{}，端口{}的线程\n".format(addr[0], addr[1])
            self.textEdit_information.insertPlainText(info)
            self.net_connect_btn.setEnabled(False)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
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
            print("{}号前端相机未连接，请检查线路后重启".format(1))

    # 打开第2个线程
    def connectnet2(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[2]
        self.thread2 = RecImgThread(addr, index=2)
        if self.thread2.working == False:  # 没有打开
            info = "打开IP：{}，端口：{} 失败\n".format(addr[0], addr[1])
            self.textEdit_information.insertPlainText(info)
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread2.isClear.connect(self.Imgsw2)
            self.thread2.start()
            # 显示线程信息
            info = "打开了地址{}，端口{}的线程\n".format(addr[0], addr[1])
            self.textEdit_information.insertPlainText(info)
            self.net_connect_btn2.setEnabled(False)

        # slot函数，接收线程信号，显示图像在控件label_imgsw_2框中
    def Imgsw2(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
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
            print("{}号前端相机未连接，请检查线路后重启".format(2))

    # 实现connectnet函数，textEdit是我们放上去的文本框的id
    # btn响应函数
    def connectnet3(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[3]
        self.thread3 = RecImgThread(addr=addr, index=3)
        if self.thread3.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开IP：{}，端口：{} 失败\n".format(addr[0], addr[1]))
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread3.isClear.connect(self.Imgsw3)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread3.start()
            # 显示线程信息
            info = "打开了地址{}，端口{}的线程\n".format(addr[0], addr[1])
            self.textEdit_information.insertPlainText(info)
            self.net_connect_btn.setEnabled(False)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw3(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
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
            print("{}号前端相机未连接，请检查线路后重启".format(3))

    def connectnet4(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[4]
        self.thread4 = RecImgThread(addr=addr, index=4)
        if self.thread4.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开IP：{}，端口：{} 失败\n".format(addr[0], addr[1]))
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread4.isClear.connect(self.Imgsw4)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread4.start()
            # 显示线程信息
            info = "打开了地址{}，端口{}的线程\n".format(addr[0], addr[1])
            self.textEdit_information.insertPlainText(info)
            self.net_connect_btn.setEnabled(False)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw4(self, isClear):
        global imgdecode  # 声明使用的全局变量
        # 如果没有异物
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
            print("{}号前端相机未连接，请检查线路后重启".format(4))

    def connectnet5(self):
        # 新建线程，传入参数
        addr = self.addr_imgs[5]
        self.thread5 = RecImgThread(addr=addr, index=5)
        if self.thread5.working == False:  # 没有打开
            self.textEdit_information.insertPlainText("打开IP：{}，端口：{} 失败\n".format(addr[0], addr[1]))
        else:
            # 连接接收子进程的isClear signal和slot函数
            self.thread5.isClear.connect(self.Imgsw5)
            # 开启子线程，子线程运行run函数定义的内容
            self.thread5.start()
            # 显示线程信息
            info = "打开了地址{}，端口{}的线程\n".format(addr[0], addr[1])
            self.textEdit_information.insertPlainText(info)
            self.net_connect_btn.setEnabled(False)

    # slot函数，接收线程信号，显示图像在第一个图像框中
    def Imgsw5(self, isClear):
        global imgdecode  # 声明使用的全局变量
        ## test code
        # for i in [1,3,4,5]:
        #     cv2.imshow("{}号相机".format(i), imgdecode[i])
        #     cv2.waitKey(1)
        # 如果没有异物
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
            print("{}号前端相机未连接，请检查线路后重启".format(5))

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
            self.label_imgsw_2.setPixmap(QPixmap.fromImage(imageblack))
        if(self.labelimg1==self.labelimg3 and self.labelimg1 != -1):
            self.labelimg3=-1
            self.label_imgsw_3.setPixmap(QPixmap.fromImage(imageblack))
        if(self.labelimg2==self.labelimg3 and self.labelimg2 != -1):
            self.labelimg3=-1
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

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main_form = Main_Form()
    with open("interface.qss") as f:
        qss = f.read()
    app.setStyleSheet(qss)
    main_form.show()
    sys.exit(app.exec_())