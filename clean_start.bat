@echo off
echo CLEAN START - Web SSH Client

taskkill /F /IM python.exe >nul 2>&1

rmdir /S /Q instance
rmdir /S /Q __pycache__

mkdir instance

echo DONE

@REM Application : Web SSH Client
@REM This application build with Python3 for access server via web SSH
@REM Build by : herdiana3389 (https://sys-ops.id)
@REM License : MIT (Open Source)
@REM Repository : https://hub.docker.com/r/sysopsid/web-ssh-client