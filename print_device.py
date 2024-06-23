from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QDialog, QListWidgetItem, QListWidget, \
    QVBoxLayout


class PrintDevice(object):
    id:str
    name:str
    description:str
    status:int

    def __init__(self, id: str, name: str, description: str, status: int):
        self.id = id
        self.name = name
        self.description = description
        self.status = status
# 单个打印作业类
class PrintJob(object):
    def __init__(self, id, document_name, start_time, job_status, pages_printed, page_count):
        self.id = id
        self.document_name = document_name
        self.start_time = start_time
        self.job_status = job_status
        self.pages_printed = pages_printed
        self.page_count = page_count


class PrintDeviceStatus(object):
    id:str
    printName:str
    printDescription:str
    statusTypeMessage:str
    listNums:int
    statusType:int # 0为不正常
    printJobs:[PrintJob]

    def __init__(self,id,printName,printDescription,statusTypeMessage,listNums,statusType,printJobs):
        self.id = id
        self.printName = printName
        self.printDescription = printDescription
        self.statusTypeMessage = statusTypeMessage
        self.listNums = listNums
        self.statusType = statusType
        self.printJobs = printJobs





# 设备选择对话框
class DeviceSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super(DeviceSelectionDialog, self).__init__(parent)
        self.devices = parent.devices
        self.selected_device = None
        self.setWindowTitle("选择设备")
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(300, 200)

        self.layout = QVBoxLayout()
        self.device_list = QListWidget()
        self.layout.addWidget(self.device_list)

        self.select_button = QPushButton("选择")
        self.select_button.clicked.connect(self.select_device)
        self.layout.addWidget(self.select_button)

        self.setLayout(self.layout)

        self.update_device_list()

    def update_device_list(self):
        self.device_list.clear()
        for device in self.devices:
            item = QListWidgetItem(device.name)
            item.setData(Qt.UserRole, device)
            self.device_list.addItem(item)

    def select_device(self):
        selected_items = self.device_list.selectedItems()
        if selected_items:
            self.selected_device = selected_items[0].data(Qt.UserRole)
            self.accept()


# 设备选择组件
class DeviceSelectionWidget(QWidget):
    def __init__(self, parent=None):
        super(DeviceSelectionWidget, self).__init__(parent)
        self.current_device = None
        self.devices = []

        layout = QHBoxLayout()

        self.select_button = QPushButton("选择设备")
        self.select_button.clicked.connect(self.show_selection_dialog)
        layout.addWidget(self.select_button)
        self.device_label = QLabel("未选择设备")
        layout.addWidget(self.device_label)
        self.device_status_t_label = QLabel("设备状态:")
        layout.addWidget(self.device_status_t_label)
        self.device_status_label = QLabel("未验证")
        layout.addWidget(self.device_status_label)
        self.device_status_num_label = QLabel("当前打印任务数:")
        layout.addWidget(self.device_status_num_label)
        self.device_status_num_va_label = QLabel("0")
        layout.addWidget(self.device_status_num_va_label)



        self.setLayout(layout)

    def set_devices(self, devices):
        self.devices = devices
    def set_current_device_show(self,device:PrintDevice):
        if device != None:
            self.current_device = device
            self.update_device_label()
    def set_device_status(self,status:str,num:int):
        self.device_status_label.setText(status)
        self.device_status_num_va_label.setText(str(num))
    def show_selection_dialog(self):
        dialog = DeviceSelectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.current_device = dialog.selected_device
            self.update_device_label()
            self.parent().update_ui_with_selected_device(self.current_device)

    def update_device_label(self):
        if self.current_device:
            self.device_label.setText(self.current_device.name)
        else:
            self.device_label.setText("未选择设备")
            self.device_status_label.setText("未知")


