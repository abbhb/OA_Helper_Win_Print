import argparse
import urllib

import requests

def upload_file(file_path, url):

    response = requests.get(url,params={"paths":f"{urllib.parse.quote(file_path)}"})

    if response.status_code == 200:
        print(f"File {file_path} uploaded successfully.")
    else:
        print(f"Failed to upload {file_path}. Status code: {response.status_code}")

def main():
    parser = argparse.ArgumentParser(description="Upload multiple files to a POST endpoint.")
    parser.add_argument('files', nargs='+', help='File paths to upload.')

    args = parser.parse_args()

    for file_path in args.files:
        upload_file(file_path, "http://127.0.0.1:9489")

if __name__ == "__main__":
    main()
