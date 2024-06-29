import ctypes
import sys
import os
import urllib
from collections import deque
from logging.handlers import TimedRotatingFileHandler
from time import sleep
from typing import List
import logging
import winreg as reg

import portalocker
from PyQt5 import QtWidgets
from plyer import notification
import multiprocessing  # For multiprocessing.freeze_support()

import requests
import json
import webbrowser
import threading
import socket

import win32print
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox, QMainWindow, QLabel, QLineEdit, \
    QPushButton, QVBoxLayout, QWidget, QListWidget, QListWidgetItem, QHBoxLayout, QTableWidget, QTableWidgetItem, \
    QDialog
from PyQt5.QtGui import QIcon, QPixmap, QImage
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QUrl, QThread, QTimer
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import shelve

from print_device import PrintDevice, DeviceSelectionWidget, PrintDeviceStatus, PrintJob, PrintDialog, PleaseLoginDialog
# 创建 logs 文件夹，如果不存在
if not os.path.exists('logs'):
    os.makedirs('logs')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# 设置日志记录
# 创建按小时滚动的处理器
handler = TimedRotatingFileHandler(
    'logs/log', when='H', interval=1, backupCount=0, encoding='utf-8'
)
handler.suffix = "%Y-%m-%d_%H.log"
handler.setLevel(logging.DEBUG)

# 设置日志格式
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# 添加处理器到日志记录器
logger.addHandler(handler)

def is_startup_enabled(app_name):
    """检查程序是否设置为开机自启"""
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, reg.KEY_READ)
        value, _ = reg.QueryValueEx(key, app_name)
        reg.CloseKey(key)
        return value == sys.executable
    except FileNotFoundError:
        return False
    except WindowsError:
        return False

def add_to_startup(app_name, app_path):
    """将程序添加到开机自启"""
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, reg.KEY_SET_VALUE)
        reg.SetValueEx(key, app_name, 0, reg.REG_SZ, app_path)
        reg.CloseKey(key)
        logging.info(f"{app_name} has been added to startup.")
    except WindowsError as e:
        logging.info(f"Failed to add to startup: {e}")


class UserInfo(object):
    username:str
    name:str
    avatar:str
    def __init__(self, username: str, name: str, avatar: str):
        self.username = username
        self.name = name
        self.avatar = avatar

class PrintJobSignal(QObject):
    new_print_job = pyqtSignal(list)
    device_update = pyqtSignal(list)
    device_status_update = pyqtSignal(object)
    reviced_print_file = pyqtSignal(str)
class LoginSignal(QObject):
    login_error = pyqtSignal(object)
    update_info = pyqtSignal(UserInfo)





class PrintJobWindow(QWidget):
    def __init__(self, files, parent=None):
        super(PrintJobWindow, self).__init__(parent)
        self.setWindowTitle('Print Job')
        self.setGeometry(100, 100, 400, 300)
        layout = QVBoxLayout()
        pass




class CurrentPrintJobWindow(QWidget):
    def __init__(self, parent=None):
        super(CurrentPrintJobWindow, self).__init__(parent)
        self.setWindowTitle('当前打印任务')
        self.setGeometry(0, 100, 600, 300)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.jobs_table_widget = QTableWidget(self)
        self.jobs_table_widget.setColumnCount(6)
        self.jobs_table_widget.setHorizontalHeaderLabels(
            ["操作", "文件名", "状态", "已印页", "剩余页","任务ID"])
        layout.addWidget(self.jobs_table_widget)
        self.setLayout(layout)
    def refresh_table(self,print_jobs:List[PrintJob]):
        self.jobs_table_widget.setRowCount(len(print_jobs))
        for row, job in enumerate(print_jobs):
            logging.info(row)
            logging.info(job)
            self.jobs_table_widget.setItem(row, 5, QTableWidgetItem(job.id))
            self.jobs_table_widget.setItem(row, 1, QTableWidgetItem(job.document_name))
            self.jobs_table_widget.setItem(row, 2, QTableWidgetItem(job.job_status))
            self.jobs_table_widget.setItem(row, 3, QTableWidgetItem(str(job.pages_printed)))
            self.jobs_table_widget.setItem(row, 4, QTableWidgetItem(str(job.page_count)))
            # 添加按钮到表格
            btn_widget = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setContentsMargins(0, 0, 0, 0)
            cancel_btn = QPushButton("取消")
            cancel_btn.clicked.connect(lambda ch, job_id=job.id: self.cancel_job(job_id))
            btn_layout.addWidget(cancel_btn)
            btn_layout.addStretch()
            btn_widget.setLayout(btn_layout)
            self.jobs_table_widget.setCellWidget(row, 0, btn_widget)

    def cancel_job(self, job_id):
        logging.info(f"取消打印作业: {job_id}")
        # 在这里添加取消打印作业的逻辑


class MainWindow(QMainWindow):
    token:str
    logged_in:bool
    print_device_list:List[PrintDevice]
    device_selected:PrintDevice
    device_selected_status:PrintDeviceStatus
    def __init__(self):
        super().__init__()
        self.logged_in = False
        self.token = None
        self.device_selected = None
        self.device_selected_status = None
        self.Pdialog = None
        self.print_job_list = deque()
        self.print_dialog_open = False

        self.print_device_list = []
        db = shelve.open('mydata.db', writeback=False)
        if 'token' in db and db['token']!='':
            self.token = db['token']
        if 'device_select' in db and db['device_select']!=None:
            self.device_selected = db['device_select']
        db.close()
        self.print_job_signal = PrintJobSignal()
        self.login_signal = LoginSignal()
        self.print_job_signal.new_print_job.connect(self.show_print_job_window)
        self.print_job_signal.device_update.connect(self.device_update)
        self.print_job_signal.device_status_update.connect(self.device_status_update)
        self.print_job_signal.reviced_print_file.connect(self.handle_file_print)
        self.login_signal.update_info.connect(self.update_user_info)
        self.login_signal.login_error.connect(self.show_login_error)
        self.init_ui()
        self.check_thread = threading.Thread(target=self.check_token)
        self.check_thread.daemon = True
        self.check_thread.start()
        # 设备轮询接口
        self.check_device_thread = threading.Thread(target=self.check_device_list)
        self.check_device_thread.daemon = True
        self.check_device_thread.start()
        # 设备状态轮询接口
        self.check_device_status_thread = threading.Thread(target=self.check_select_device)
        self.check_device_status_thread.daemon = True
        self.check_device_status_thread.start()
        # 虚拟打印机相关
        self.start_file_upload_server()

    def process_queue(self):

        if not self.print_dialog_open and self.print_job_list:
            if self.isHidden():
                self.show()
            if not self.logged_in or self.token == None:
                please_login_dialog = PleaseLoginDialog(self)
                if please_login_dialog.exec() == QDialog.Accepted:
                    # 去登陆
                    if not self.logged_in:
                        self.start_server_thread()
                        self.open_login_webpage()
                return
            file_to_print = self.print_job_list.popleft()
            self.show_dialog(file_to_print)
        else:
            pass
            # If no dialog is open and queue is empty, do further processing (e.g., write to file)

    def add_to_queue(self, file_path):
        self.print_job_list.append(file_path)
        self.process_queue()


    def show_dialog(self, file_path):
        self.print_dialog_open = True
        self.Pdialog = PrintDialog(file_path,self)
        if self.device_selected:
            self.Pdialog.set_current_device_show(self.device_selected)

        self.Pdialog.finished.connect(self.dialog_closed)
        if self.Pdialog.exec() == QDialog.Accepted:
            # 确认打印
            self.file_path = file_path
            # 异步请求
            self.send_print_request(self.Pdialog.startInput.text(),self.Pdialog.endInput.text(),self.Pdialog.directio,self.Pdialog.copiInput.text(),self.Pdialog.mode,self.Pdialog.max_pages)
            # dialog.deviceId 更新回来 添加确认的文件路径以及打印配置
            self.Pdialog = None
            pass

    def send_print_request(self,start_num,end_num,landscape,copies,duplex,total):
        if not hasattr(self, 'file_path'):
            logging.info("No file selected")
            return

        url = "http://easyoa.fun:8081/api/printer/uploadPrintFileForWindows"
        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        if self.device_selected==None:
            self.getMessageSystem("EasyOA打印", "提交打印失败!打印机选择异常")
            return

        data = {
            'copies': int(copies),
            'duplex': duplex,
            'start_num': int(start_num),
            'end_num': int(end_num),
            'landscape': landscape,
            'total': int(total),
            'device_id': self.device_selected.id
        }

        files = {
            'file': open(self.file_path, 'rb')
        }

        response = requests.post(url, headers=headers, data=data, files=files)
        if response.ok:
            self.getMessageSystem("EasyOA打印", "提交打印成功!")

        else:
            self.getMessageSystem("EasyOA打印", "提交打印失败!")
            logging.info("Failed to send logging.info request", response.status_code, response.text)
    def getMessageSystem(self,title,message):
        try:
            notification.notify(
                title=title,
                message=message,
                timeout=3  # seconds
            )
        except Exception as e:
            logging.info(e)
    def dialog_closed(self):
        self.print_dialog_open = False
        self.process_queue()
    def update_user_info(self,user_info:UserInfo):
        self.logged_in = True
        self.name_label.setText(user_info.name)
        self.username_label.setText(user_info.username)
        res = requests.get(user_info.avatar)
        img = QImage.fromData(res.content)
        self.avatar_label.setPixmap(QPixmap.fromImage(img).scaled(40, 40))
        self.statusBar().showMessage('Logged in')
        # 每次登录成功顺便检查下有没有任务在打印队列
        self.process_queue()
        pass
    def device_update(self,devices:list):
        self.print_device_list = devices
        if self.Pdialog:
            self.Pdialog.set_devices(self.print_device_list)
        self.deviceSlection.set_devices(self.print_device_list)
    def device_status_update(self,device_status:PrintDeviceStatus):
        # 设备状态更新
        if device_status != None:
            logging.info("更新111")
            self.device_selected_status = device_status
            self.deviceSlection.set_device_status(device_status.statusTypeMessage,device_status.listNums)
            if self.Pdialog:
                self.Pdialog.set_device_status(device_status.statusTypeMessage,device_status.listNums)
            logging.info(device_status.printJobs)
            self.current_print_job_window.refresh_table(device_status.printJobs)
            return
        # 更新设备异常
        self.current_print_job_window.refresh_table([])
        self.deviceSlection.set_device_status("设备连接异常,请检查!",-1)
    def show_login_error(self,obj):
        self.logged_in = False
        self.name_label.setText("点击头像登录")
        self.username_label.setText("点击头像登录")
        self.avatar_label.setPixmap(QPixmap('nologgin.png').scaled(40, 40))
        pass
    def check_token(self):
        while True:
            if self.token == None:
                # 为空每秒检查一次
                sleep(1)
            else:
                self.handle_login_token(self.token)
                sleep(10)
    def update_ui_with_selected_device(self,device):
        # 提供给选择器修改设备
        self.device_selected = device
        if self.Pdialog:
            self.Pdialog.set_current_device_show(device)
        db = shelve.open('mydata.db', writeback=False)
        db['device_select'] = device
        db.close()
    def check_device_list(self):
        while True:
            sleep(3)
            # 你的API的URL
            url = 'http://easyoa.fun:8081/api/printer/print_device%20polling'

            # 你的token
            token = self.token

            # 请求头
            headers = {
                'Content-Type': 'application/json',  # 根据API的要求设置
                'Authorization': f'Bearer {token}'
            }

            # 发送GET请求
            response = requests.get(url, headers=headers)

            # 打印响应的文本内容
            logging.info(response.text)

            # 检查响应状态码
            if response.status_code == 200:
                resp = response.json()
                if resp["code"]==1:
                    device_temps = []
                    datas = resp["data"]
                    for i in datas:
                        device_temps.append(PrintDevice(i["id"],i["name"],i["description"],i["status"]))
                    # 成功
                    self.print_job_signal.device_update.emit(device_temps)
                    continue
            # 不成功便成仁 清空
            self.print_job_signal.device_update.emit([])

    def check_select_device(self):
        # 独立线程
        while True:
            sleep(1.5)
            if self.device_selected==None:
                continue
            # 你的API的URL
            url = 'http://easyoa.fun:8081/api/printer/print_device_info%20polling/'+ str(self.device_selected.id)

            # 你的token
            token = self.token

            # 请求头
            headers = {
                'Content-Type': 'application/json',  # 根据API的要求设置
                'Authorization': f'Bearer {token}'
            }

            # 发送GET请求
            response = requests.get(url, headers=headers)

            # 打印响应的文本内容
            logging.info(response.text)

            # 检查响应状态码
            if response.status_code == 200:
                resp = response.json()
                if resp["code"]==1:
                    datas = resp["data"]
                    jobs = []
                    for i in datas["printJobs"]:
                        job = PrintJob(i["id"],i["documentName"],i["startTime"],i["jobStatus"],i["pagesPrinted"],i["pageCount"])
                        jobs.append(job)
                    prints = PrintDeviceStatus(datas["id"],datas["printName"],datas["printDescription"],datas["statusTypeMessage"],datas["listNums"],datas["statusType"],jobs)
                    # 成功
                    self.print_job_signal.device_status_update.emit(prints)
                    continue
            # 不成功便成仁 清空
            self.print_job_signal.device_status_update.emit(None)

        pass
    def init_ui(self):
        self.setWindowTitle('Main Window')
        self.setGeometry(400, 200, 600, 400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setWindowIcon(QIcon('icon.png'))
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon('icon.png'))
        self.tray_icon.activated[QtWidgets.QSystemTrayIcon.ActivationReason].connect(self.openMainWindow)

        tray_menu = QMenu()
        open_action = QAction("打开EasyOA打印管理", self)
        open_action.triggered.connect(self.show)
        tray_menu.addAction(open_action)

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)

        self.tray_icon.show()

        self.statusBar().showMessage('Ready')

        # Top bar for user information
        self.top_bar = QHBoxLayout()
        self.avatar_label = QLabel(self)
        self.avatar_label.setPixmap(QPixmap('nologgin.png').scaled(40, 40))
        self.avatar_label.mousePressEvent = self.avatar_clicked
        self.name_label = QLabel('Name: 点击头像登录')
        self.username_label = QLabel('Username: -')

        self.top_bar.addWidget(self.avatar_label)
        self.top_bar.addWidget(self.name_label)
        self.top_bar.addWidget(self.username_label)

        top_bar_widget = QWidget()
        top_bar_widget.setLayout(self.top_bar)
        self.setMenuWidget(top_bar_widget)
        self.deviceSlection = DeviceSelectionWidget(self)
        self.deviceSlection.setFixedWidth(400)
        self.deviceSlection.setGeometry(20,30,400,100)
        self.deviceSlection.set_devices(self.print_device_list)
        self.deviceSlection.show()
        self.deviceSlection.set_current_device_show(self.device_selected)

        self.current_print_job_window = CurrentPrintJobWindow(self)
        self.current_print_job_window.show()
    def avatar_clicked(self, event):
        if not self.logged_in:
            self.start_server_thread()
            self.open_login_webpage()
    def openMainWindow(self,reason):
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick:
            self.show()

    def open_login_webpage(self):
        webbrowser.open('http://easyoa.fun:8081/#/login?redirect=ClientOauth')

    def attempt_login(self, username, password):
        # Replace with your login logic
        if username == "admin" and password == "password":
            self.logged_in = True
            self.name_label.setText('Name: Admin')
            self.username_label.setText('Username: admin')
            self.statusBar().showMessage('Logged in')
            return True
        return False



    def handle_print_job(self, files):
        if not self.logged_in:
            # 弹出你还没登录
            return
        self.print_job_signal.new_print_job.emit(files)

    def show_print_job_window(self, files):
        self.print_job_window = PrintJobWindow(files, self)
        self.print_job_window.show()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def start_file_upload_server(self):

        self.server_thread_upload = threading.Thread(target=self.server_thread_upload_file_func)
        self.server_thread_upload.daemon = True
        self.server_thread_upload.start()
    def start_server_thread(self):

        self.server_thread = threading.Thread(target=self.server_thread_func)
        self.server_thread.daemon = True
        self.server_thread.start()

    def server_thread_func(self):
        class RequestHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                query = urlparse(self.path).query
                params = parse_qs(query)
                if 'token' in params:
                    token = params['token'][0]
                    self.send_response_only(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'Login successful, you can close this window.')
                    self.server.handle_code_received(token)

        class CustomHTTPServer(HTTPServer):
            def __init__(self, server_address, RequestHandlerClass, main_window):
                super().__init__(server_address, RequestHandlerClass)
                self.main_window = main_window

            def handle_code_received(self, token):
                self.main_window.handle_login_token(token)
        logging.info("启动")
        multiprocessing.freeze_support()

        httpd = CustomHTTPServer(('localhost', 65431), RequestHandler, self)
        httpd.serve_forever()
        logging.info("启动1")




    def server_thread_upload_file_func(self):
        class RequestHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                query = urlparse(self.path).query
                params = parse_qs(query)
                if 'paths' in params:
                    paths = params['paths'][0]
                    self.send_response_only(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'successful')
                    decoded_path = urllib.parse.unquote(paths)

                    self.server.handle_code_received(decoded_path)

        class CustomHTTPServer(HTTPServer):
            def __init__(self, server_address, RequestHandlerClass, main_window):
                super().__init__(server_address, RequestHandlerClass)
                self.main_window = main_window

            def handle_code_received(self, path):
                self.main_window.print_job_signal.reviced_print_file.emit(path)

        multiprocessing.freeze_support()

        httpd = CustomHTTPServer(('127.0.0.1', 9489), RequestHandler, self)
        httpd.serve_forever()

    def handle_file_print(self,path):
        # 能拿到pdf文件路径 直接执行打印，此处需要有队列，一个个处理弹窗，如果当前正在弹窗就等待直接添加到list里，每次弹窗结束前会查看list是否存在任务，如果有任务就继续执行最先的任务
        logging.info(path)
        self.add_to_queue(path)

    def handle_login_token(self, token):
        # Save the token and update the UI
        logging.info(f"token:{token}")
        # 此token为java后端自用token不是oauth2的access_token,此token能直接拿到用户id
        # 接口的 URL
        url = 'http://easyoa.fun:8081/api/user/info'

        # 构造请求头，添加 Authorization: Bearer token
        headers = {
            'Content-Type': 'application/json',  # 根据 API 的要求设置
            'Authorization': f'Bearer {token}'
        }

        # 发送 POST 请求
        response = requests.post(url, headers=headers)
        self.token = token
        db = shelve.open('mydata.db', writeback=False)
        db['token'] = token
        db.close()

        # 检查响应状态码
        if response.status_code == 200:
            # 请求成功，打印响应内容
            resp = response.json()
            logging.info('用户信息：', resp)
            if resp["code"] == 1:
                userinfo = UserInfo(
                    username=resp["data"]["username"],
                    name=resp["data"]["name"],
                    avatar=resp["data"]["avatar"]
                )
                self.login_signal.update_info.emit(userinfo)
                logging.info("登录成功")
                return
            if resp["code"] == 900:
                # token过期了
                self.token = None
        self.login_signal.login_error.emit(None)




def main():
    app_name = "EasyOA"  # 你可以根据需要更改应用程序名称
    app_path = os.path.abspath(sys.argv[0])

    if not is_startup_enabled(app_name):
        add_to_startup(app_name, app_path)
    else:
        logging.info(f"{app_name} is already set to run at startup.")
    app = QApplication(sys.argv)
    main_window = MainWindow()
    # main_window.check_login()


    sys.exit(app.exec_())


if __name__ == '__main__':
    lock_file = "app.lock"
    try:
        lock = open(lock_file, 'w')
        portalocker.lock(lock, portalocker.LOCK_EX | portalocker.LOCK_NB)
    except portalocker.LockException:
        logging.info("Another instance is already running")
        sys.exit(0)
    main()
