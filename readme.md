# 打包完别忘复制图标等资源文件，否则无法启动

# http服务器在pyqt5里打包引起的bug 无法启动
https://github.com/pyinstaller/pyinstaller/issues/8210

# 打包命令
pyinstaller -D -w -i icon.png  --uac-admin main.py