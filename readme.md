# 打包完别忘复制图标等资源文件，否则无法启动

# http服务器在pyqt5里打包引起的bug 无法启动
https://github.com/pyinstaller/pyinstaller/issues/8210

# 打包命令
pyinstaller -D -w -i icon.png  --uac-admin main.py


# 说明
本项目无法独立使用，需配合clawpdf提供的虚拟打印机，通过重编译将其默认打印动作改成执行[upload_files.py](upload_files.py)的打包后的exe去发请求来调用本程序处理后续，转pdf的过程是clawpdf完成的，完成后的pdf才会传回一个路径url
所以可以代码仓库里找一下改版后的clawpdf，是c#写的,最终本程序放入里面的安装器并创建快捷方式，放入启动目录实现开机自启等等.



理论来说公版的clawpdf也能用，手动去设置里修改动作为执行[upload_files.py](upload_files.py)打包完的exe并带上处理完pdf的路径作为参数即可，clawpdf设置为静默处理，也就是当word等程序通过虚拟打印机打印自动完成转pdf，无需人工干预，成功后跳入我们的程序再接管
