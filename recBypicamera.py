import io
import socket
import struct
from PIL import Image
import cv2
import numpy as np

# 启动socket，设置监听端口为8000，接受所有ip的连接
server_socket = socket.socket()
server_socket.bind(('192.168.1.112', 9999))
server_socket.listen(0)

# 接受一个客户端连接
connection = server_socket.accept()[0].makefile('rb')
try:
    while True:
        # 读取我们的包头，也就是图片的长度
        # 如果长度为0则退出循环
        image_len = struct.unpack('<L', connection.read(struct.calcsize('<L')))[0]
        if not image_len:
            break
        # 构造一个流来接受客户端传输的数据
        # 开始接收数据并写入流
        image_stream = io.BytesIO()
        image_stream.write(connection.read(image_len))
        # 将流的指针指向开始处，并通过PIL来读入流
        # 并将之存储到文件
        image_stream.seek(0)
        buff = np.fromstring(image_stream.getvalue(), dtype=np.uint8)
        image = cv2.imdecode(buff, 1)
        cv2.imshow('1', image)
        if cv2.waitKey(1) == 27:
            break
        print('ok')
        # image = Image.open(image_stream)
        # print('Image is %dx%d' % image.size)
        # image.verify()
        # print('Image is verified')
        # image.show()
finally:
    connection.close()
    server_socket.close()
