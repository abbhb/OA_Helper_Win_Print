import sys
import os
from time import sleep
from typing import List

import requests
import json
import webbrowser
import threading
import socket
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox, QMainWindow, QLabel, QLineEdit, \
    QPushButton, QVBoxLayout, QWidget, QListWidget, QListWidgetItem, QHBoxLayout, QTableWidget, QTableWidgetItem
from PyQt5.QtGui import QIcon, QPixmap, QImage
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QUrl, QThread
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import shelve

from print_device import PrintDevice, DeviceSelectionWidget, PrintDeviceStatus, PrintJob


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
    device_status_update = pyqtSignal(PrintDeviceStatus)
class LoginSignal(QObject):
    login_error = pyqtSignal()
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
            print(row)
            print(job)
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
        print(f"取消打印作业: {job_id}")
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

    def update_user_info(self,user_info:UserInfo):
        self.logged_in = True
        self.name_label.setText(user_info.name)
        self.username_label.setText(user_info.username)
        res = requests.get(user_info.avatar)
        img = QImage.fromData(res.content)
        self.avatar_label.setPixmap(QPixmap.fromImage(img).scaled(40, 40))
        self.statusBar().showMessage('Logged in')

        pass
    def device_update(self,devices:list):
        self.print_device_list = devices
        self.deviceSlection.set_devices(self.print_device_list)
    def device_status_update(self,device_status:PrintDeviceStatus):
        # 设备状态更新
        if device_status != None:
            print("更新111")
            self.device_selected_status = device_status
            self.deviceSlection.set_device_status(device_status.statusTypeMessage,device_status.listNums)
            print(device_status.printJobs)
            self.current_print_job_window.refresh_table(device_status.printJobs)
            return
        # 更新设备异常
        self.current_print_job_window.refresh_table([])
        self.deviceSlection.set_device_status("设备连接异常,请检查!",-1)
    def show_login_error(self):
        self.logged_in = False
        self.name_label.setText("点击头像登录")
        self.username_label.setText("点击头像登录")
        self.avatar_label.setPixmap(QPixmap('icon.png').scaled(40, 40))
        pass
    def check_token(self):
        while True:
            if self.token == None:
                sleep(5)
            else:
                self.handle_login_token(self.token)
                sleep(30)
    def update_ui_with_selected_device(self,device):
        # 提供给选择器修改设备
        self.device_selected = device
        db = shelve.open('mydata.db', writeback=False)
        db['device_select'] = device
        db.close()
    def check_device_list(self):
        while True:
            sleep(5)
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
            print(response.text)

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
            sleep(2)
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
            print(response.text)

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
        self.setGeometry(100, 100, 600, 400)

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon('icon.png'))

        tray_menu = QMenu()
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.show)
        tray_menu.addAction(open_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        self.statusBar().showMessage('Ready')

        # Top bar for user information
        self.top_bar = QHBoxLayout()
        self.avatar_label = QLabel(self)
        self.avatar_label.setPixmap(QPixmap('icon.png').scaled(40, 40))
        self.avatar_label.mousePressEvent = self.avatar_clicked
        self.name_label = QLabel('Name: Not Logged In')
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

    def open_login_webpage(self):
        webbrowser.open('http://easyoa.fun:8081/#/client_oauth')

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
                    self.send_response(200)
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

        httpd = CustomHTTPServer(('localhost', 65431), RequestHandler, self)
        httpd.serve_forever()





    def handle_login_token(self, token):
        # Save the token and update the UI
        print(f"token:{token}")
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
            print('用户信息：', resp)
            if resp["code"] == 1:
                userinfo = UserInfo(
                    username=resp["data"]["username"],
                    name=resp["data"]["name"],
                    avatar=resp["data"]["avatar"]
                )
                self.login_signal.update_info.emit(userinfo)
                print("登录成功")
                return
            if resp["code"] == 900:
                # token过期了
                self.token = None
        self.login_signal.login_error.emit()





def main():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    # main_window.check_login()

    # Simulate receiving a print job with file list
    # main_window.handle_print_job(['file1.pdf', 'file2.pdf'])

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
