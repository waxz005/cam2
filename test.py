import  numpy as np
import cv2
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import *
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QDockWidget, QListWidget

def image_process():
    # image = np.zeros((480, 640, 3), np.uint8)
    # print (image.dtype, image.shape[0], image.shape[1], image.shape[2], image.ctypes)
    # qimg = QImage(image.data, image.shape[1], image.shape[0], image.shape*image*3, QImage,Format_RGB888)
    img = cv2.imread('C:/Users/Administrator/Desktop/depth.png', cv2.IMREAD_GRAYSCALE)
    ifo = img.shape
    dep = img.
    print (ifo)

    # print(ifo[0], ifo[1], ifo[2])
    cv2.imshow('image', img)
    cv2.waitKey(0)


if __name__ == "__main__":
    image_process()
