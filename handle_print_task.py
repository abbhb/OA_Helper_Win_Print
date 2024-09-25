import sys

def handle_print_task(file_path):
    with open(file_path, 'r') as file:
        data = file.read()
        print(f"Received print task: {data}")
        # 处理打印任务，例如将其保存为 PDF

if __name__ == "__main__":
    if len(sys.argv) > 1:
        handle_print_task(sys.argv[1])
    else:
        print("No file path provided.")
