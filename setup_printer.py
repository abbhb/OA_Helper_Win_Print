import subprocess
import win32print
import win32api


def create_virtual_printer(printer_name, port_name):
    # 检查打印机是否已经存在
    printers = [printer[2] for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
    if printer_name in printers:
        print(f"Printer '{printer_name}' already exists.")
        return

    # 创建新的打印机并将其端口设置为重定向端口
    cmd = (
        f'rundll32 printui.dll,PrintUIEntry /if /b "{printer_name}" '
        f'/f "%windir%\\inf\\ntprint.inf" /r "{port_name}" /m "Generic / Text Only"'
    )
    result = subprocess.run(cmd, shell=True)
    if result.returncode == 0:
        print(f"Printer '{printer_name}' installed successfully.")
    else:
        print(f"Failed to install printer '{printer_name}'.")


def setup_redmon_port(port_name, program_path):
    # 使用 RedMon 配置端口
    redmon_config = [
        '[Port]',
        f'PortName={port_name}',
        f'RedirectPort={program_path} %1',
        'PromptForName=FALSE',
        'PrinterName=',
        'RunUserInterface=FALSE',
        'Copies=1',
    ]
    port_file = f"C:\\Windows\\System32\\spool\\drivers\\w32x86\\3\\{port_name}.PRT"
    with open(port_file, 'w') as f:
        f.write("\n".join(redmon_config))
    print(f"RedMon port '{port_name}' configured successfully.")


if __name__ == '__main__':
    printer_name = "Easy OA Printer"
    port_name = "RPT2:"
    program_path = r"D:\pycode\print_win\dist\handle_print_task.exe"

    create_virtual_printer(printer_name, port_name)
    setup_redmon_port(port_name, program_path)
