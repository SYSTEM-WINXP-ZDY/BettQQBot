@echo off
echo �����ļ�ȫ�ı����ܹ��� (���ֶμ��ܹ���)
echo ==================================================================

REM ����Ƿ�װ��Python
D:\Python\python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ����: δ�ҵ�Python��װ. ��ȷ��Python�Ѱ�װ����ϵͳPATH��.
    pause
    exit /b 1
)

REM ����Ƿ��ṩ�������ļ�
if "%~1"=="" (
    echo ��ָ��Ҫ���ܵ������ļ���
    echo �÷�: %~nx0 [�����ļ�] [����ļ�]
    echo ����: %~nx0 config.yaml
    echo ����: %~nx0 config.yaml config.encrypted.yaml
    pause
    exit /b 1
)

set INPUT_FILE=%~1
set OUTPUT_FILE=%~2

if "%OUTPUT_FILE%"=="" (
    REM ���δָ������ļ�����ʹ���������ļ���ͬ��·�������.encrypted��׺
    set OUTPUT_FILE=%INPUT_FILE%.encrypted
)

echo ����: �˹��߽��������ļ��е������ı����ݽ��м��ܣ�
echo �����ı����Զ�ʹ�÷ֶμ��ܣ�ÿ��Լ20���ַ�����
echo.
echo �����ļ�: %INPUT_FILE%
echo ����ļ�: %OUTPUT_FILE%
echo ԭʼ����: %INPUT_FILE%.original
echo.
set /p confirm=�Ƿ����? (Y/N): 

if /i "%confirm%" NEQ "Y" (
    echo ������ȡ��.
    pause
    exit /b 0
)

set FORCE_OPTION=--force
echo ��Ĭ������ǿ��ģʽ��

set SKIP_OPTION=
set /p skip_confirm=�Ƿ������Ѱ����������ݵ��ļ��� (Y/N): 
if /i "%skip_confirm%" EQU "Y" (
    set SKIP_OPTION=--skip-encrypted
    echo �����������Ѽ����ļ�ѡ�
)

REM ���м��ܽű�
D:\Python\python encrypt_all_text.py %FORCE_OPTION% %SKIP_OPTION% "%INPUT_FILE%" "%OUTPUT_FILE%"

if %errorlevel% neq 0 (
    echo �����ļ�����ʧ�ܣ�
    pause
) else (
    echo.
    echo ������ɣ������ı���ʹ�÷ֶμ��ܣ�ÿ��Լ20���ַ�����
    echo ԭʼ�ļ�����: %INPUT_FILE%.original
    echo ���ܺ��ļ�: %OUTPUT_FILE%
    if "%OUTPUT_FILE%"=="config.yaml" echo ����������֤���ļ�: config.backup.yaml
    echo.
    echo �����ڿ���ʹ�ü��ܺ�������ļ��ˡ�
    pause
) 