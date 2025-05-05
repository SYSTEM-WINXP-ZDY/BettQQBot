@echo off
:start
Python.exe main.py
echo ————————————————————————
echo %data%|%time%重启.
echo 日志已保存到logs\
echo ————————————————————————
ping 127.0.0.1 -n 3
goto start