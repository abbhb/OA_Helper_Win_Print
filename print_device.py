import io
import math

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIntValidator, QPixmap, QImage
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QDialog, QListWidgetItem, QListWidget, \
    QVBoxLayout, QMessageBox, QLineEdit, QButtonGroup, QRadioButton, QScrollArea, QDialogButtonBox
import fitz
from PIL import Image, ImageDraw


class PrintDevice(object):
    id: str
    name: str
    description: str
    status: int

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
    id: str
    printName: str
    printDescription: str
    statusTypeMessage: str
    listNums: int
    statusType: int  # 0为不正常
    printJobs: [PrintJob]

    def __init__(self, id, printName, printDescription, statusTypeMessage, listNums, statusType, printJobs):
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

    def set_current_device_show(self, device: PrintDevice):
        if device != None:
            self.current_device = device
            self.update_device_label()

    def set_device_status(self, status: str, num: int):
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


class PrintDialog(QDialog):
    def __init__(self, file_path, parent=None):
        super(PrintDialog, self).__init__(parent)
        self.setWindowTitle('Print Dialog')
        self.main_layout_a = QHBoxLayout()
        self.layout = QVBoxLayout()
        self.file_path = file_path
        self.max_pages = 1
        self.mode = 1
        self.directio = 0
        ok_img,total_pages = pdf2image(file_path,1024,3,1024,(0,0))
        self.max_pages = int(total_pages)
        self.ok_img = ok_img
        message_label = QLabel()
        message_label.setText(f"Do you want to print {file_path}?")
        self.layout.addWidget(message_label)

        self.deviceSelectionWidget = DeviceSelectionWidget()
        self.layout.addWidget(self.deviceSelectionWidget)



        start_tip = QLabel("起始页码")
        # 创建一个QLineEdit，用于输入数字
        self.startInput = QLineEdit(self)

        # 设置输入验证器，限制只能输入整数
        self.startInput.setValidator(QIntValidator(1, self.max_pages,self))
        self.layout.addWidget(start_tip)
        self.layout.addWidget(self.startInput)
        self.startInput.setText('1')

        end_tip = QLabel("结束页码")
        # 创建一个QLineEdit，用于输入数字
        self.endInput = QLineEdit(self)
        # 设置输入验证器，限制只能输入整数
        self.endInput.setValidator(QIntValidator(1, self.max_pages,self))
        self.endInput.setText(str(self.max_pages))
        self.layout.addWidget(end_tip)
        self.layout.addWidget(self.endInput)
        copi_tip = QLabel("份数")
        self.copiInput = QLineEdit(self)
        # 设置输入验证器，限制只能输入整数
        self.copiInput.setValidator(QIntValidator(1, 99,self))
        self.layout.addWidget(copi_tip)
        self.layout.addWidget(self.copiInput)
        self.copiInput.setText('1')

        # 创建打印方向的表单项
        self.directionGroup = QButtonGroup(self)
        directionLabel = QLabel("打印方向:")
        self.verticalRadio = QRadioButton("竖直")
        self.horizontalRadio = QRadioButton("横向")
        self.directionGroup.addButton(self.verticalRadio, 0)
        self.verticalRadio.setChecked(True)

        self.directionGroup.addButton(self.horizontalRadio, 1)
        self.layout.addWidget(directionLabel)
        self.layout.addWidget(self.verticalRadio)
        self.layout.addWidget(self.horizontalRadio)
        self.verticalRadio.clicked.connect(self.onButtonverticalRadioClickedDir)
        self.horizontalRadio.clicked.connect(self.onButtonhorizontalRadioClickedDir)

        # 创建打印模式的表单项
        self.modeGroup = QButtonGroup(self)
        modeLabel = QLabel("打印模式:")
        self.singleSideRadio = QRadioButton("单面打印")
        self.duplexRadio = QRadioButton("双面打印")
        self.duplexUpsideRadio = QRadioButton("双面向上翻打印")
        self.singleSideRadio.setChecked(True)
        self.modeGroup.addButton(self.singleSideRadio, 1)
        self.modeGroup.addButton(self.duplexRadio, 2)
        self.modeGroup.addButton(self.duplexUpsideRadio, 3)
        self.layout.addWidget(modeLabel)
        self.layout.addWidget(self.singleSideRadio)
        self.layout.addWidget(self.duplexRadio)
        self.layout.addWidget(self.duplexUpsideRadio)
        self.singleSideRadio.clicked.connect(self.onButtonClicked1)
        self.duplexRadio.clicked.connect(self.onButtonClicked2)
        self.duplexUpsideRadio.clicked.connect(self.onButtonClicked3)

        print_button = QPushButton('确认打印')
        print_button.clicked.connect(self.print_file)
        self.layout.addWidget(print_button)

        cancel_button = QPushButton('取消')
        cancel_button.clicked.connect(self.reject)
        self.layout.addWidget(cancel_button)

        # 右侧布局
        self.right_layout = QVBoxLayout()
        self.image_label = QLabel(self)

        pixmap = self.convert_pil_to_pixmap(self.ok_img).scaled(800, 800, Qt.KeepAspectRatio)
        self.image_label.setPixmap(pixmap)
        self.image_label.mousePressEvent = self.show_large_image
        self.right_layout.addWidget(self.image_label)

        # 将左侧和右侧布局添加到主布局中
        self.main_layout_a.addLayout(self.layout, 1)  # 左侧布局，占1份
        self.main_layout_a.addLayout(self.right_layout, 2)  # 右侧布局，占2份
        self.setLayout(self.main_layout_a)


    def set_devices(self, devices):
        # self.devices = devices
        self.deviceSelectionWidget.set_devices(devices)


    def set_current_device_show(self, device: PrintDevice):
        if device != None:
            self.deviceSelectionWidget.set_current_device_show(device)

    def update_ui_with_selected_device(self, device):
        # 提供给选择器修改设备
        # self.device_selected = device
        self.parent().update_ui_with_selected_device(device)


    def set_device_status(self, status: str, num: int):
        self.deviceSelectionWidget.set_device_status(status,num)


    def show_large_image(self, event):
        self.large_image_window = QDialog(self)
        self.large_image_window.setWindowTitle("源文件预览")
        self.large_image_window.setGeometry(100,50,1440,900)
        layout = QVBoxLayout()
        scroll_area = QScrollArea()
        large_image_label = QLabel()
        pixmap = self.convert_pil_to_pixmap(self.ok_img).scaled(1024, 1024, Qt.KeepAspectRatio)
        large_image_label.setPixmap(pixmap)
        scroll_area.setWidget(large_image_label)
        layout.addWidget(scroll_area)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.large_image_window.accept)
        layout.addWidget(button_box)
        self.large_image_window.s1etLayout(layout)
        self.large_image_window.exec_()
    def onButtonClicked1(self, button):
        # 获取被点击的按钮的ID
        self.mode = 1
    def onButtonClicked2(self, button):
        # 获取被点击的按钮的ID
        self.mode = 2
    def onButtonClicked3(self):
        # 获取被点击的按钮的ID
        self.mode = 3
    def convert_pil_to_pixmap(self, pil_image):
        # Convert PIL image to byte data
        byte_data = io.BytesIO()
        pil_image.save(byte_data, format='PNG')
        byte_data = byte_data.getvalue()

        # Convert byte data to QImage
        qimage = QImage.fromData(byte_data)

        # Convert QImage to QPixmap
        pixmap = QPixmap.fromImage(qimage)
        return pixmap
    def onButtonverticalRadioClickedDir(self):
        self.directio = 0

    def onButtonhorizontalRadioClickedDir(self):
        self.directio = 1
    def print_file(self):
        # Here you would implement your printing logic
        print(f"Printing file: {self.file_path}")
        self.accept()

def pdf2image(pdf_file_path: str, min_width: int, num_cols: int = 3, unit_width: int = 1024,
                  padding: tuple = (0, 0)):
        """从PDF提取指定页，转为PIL图片对象。"""
        i = 0
        with fitz.open(pdf_file_path) as doc:
            images = []
            for page in doc:
                # a resolution to ensure the output width not less than `min_width`
                *_, w, h = page.rect
                res = max(min_width / w, 1.0)
                pix = page.get_pixmap(matrix=fitz.Matrix(res, res))
                print(pix.width)
                print(pix.height)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)
                i = i + 1
                if i == 9:
                    break
            ok_img = join_images_with_borders(images, num_cols, unit_width, padding)
            # 创建一个可以在给定图像上绘图的对象

            print("总页数：" + str(len(doc)))
            return ok_img, str(len(doc))

def join_images_with_borders(images: list, num_cols: int, unit_width: int, padding: tuple, line_color=(255, 0, 0), line_width=5):
    """拼接PIL图片列表，返回拼接后的PIL图片对象，并添加全包裹的红色框线。"""
    # final size
    num_rows = math.ceil(len(images) / num_cols)
    max_aspect = max(img.size[1] / img.size[0] for img in images)  # max aspect ratio
    unit_height = int(unit_width * max_aspect)

    width = (unit_width + padding[0] + line_width) * num_cols - padding[0] + line_width
    height = (unit_height + padding[1] + line_width) * num_rows - padding[1] + line_width
    final_img = Image.new('RGB', (width, height), (255, 255, 255))  # white and empty image

    # Create border image
    border_img = Image.new('RGB', (unit_width + 2 * line_width, unit_height + 2 * line_width), (255, 255, 255))
    for i in range(line_width):
        border_img.paste(Image.new('RGB', (unit_width + 2 * line_width - 2 * i, line_width), line_color), (i, i))
        border_img.paste(Image.new('RGB', (unit_width + 2 * line_width - 2 * i, line_width), line_color), (i, unit_height + line_width - i))
        border_img.paste(Image.new('RGB', (line_width, unit_height + 2 * line_width - 2 * i), line_color), (i, i))
        border_img.paste(Image.new('RGB', (line_width, unit_height + 2 * line_width - 2 * i), line_color), (unit_width + line_width - i, i))

    # assign image to the right position one by one
    for i_row in range(num_rows):
        for i_col in range(num_cols):
            pos = num_cols * i_row + i_col
            if pos >= len(images):
                break

            img = images[pos]
            img.thumbnail((unit_width, unit_height), resample=Image.ANTIALIAS)
            paste_x = (unit_width + padding[0] + line_width) * i_col + line_width
            paste_y = (unit_height + padding[1] + line_width) * i_row + line_width
            final_img.paste(border_img, (paste_x - line_width, paste_y - line_width))
            final_img.paste(img, (paste_x, paste_y))

    return final_img
class PleaseLoginDialog(QDialog):
    def __init__(self, parent=None):
        super(PleaseLoginDialog, self).__init__(parent)
        self.setWindowTitle('请先登录!')
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        message_label = QMessageBox()
        message_label.setText(f"您还没有登录，点击登录成功后即可继续打印操作!")
        self.layout.addWidget(message_label)

        print_button = QPushButton('登录【如果失败点击头像重登录即可】')
        print_button.clicked.connect(self.to_login)
        self.layout.addWidget(print_button)

        cancel_button = QPushButton('就不登录（文件会在本地队列里面）')
        cancel_button.clicked.connect(self.reject)
        self.layout.addWidget(cancel_button)

    def to_login(self):
        # Here you would implement your printing logic
        print("点击了登录")
        self.accept()
