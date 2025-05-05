@echo off
echo 配置文件全文本加密工具 (带分段加密功能)
echo ==================================================================

REM 检查是否安装了Python
D:\Python\python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Python安装. 请确认Python已安装且在系统PATH中.
    pause
    exit /b 1
)

REM 检查是否提供了输入文件
if "%~1"=="" (
    echo 请指定要加密的配置文件！
    echo 用法: %~nx0 [输入文件] [输出文件]
    echo 例如: %~nx0 config.yaml
    echo 或者: %~nx0 config.yaml config.encrypted.yaml
    pause
    exit /b 1
)

set INPUT_FILE=%~1
set OUTPUT_FILE=%~2

if "%OUTPUT_FILE%"=="" (
    REM 如果未指定输出文件，则使用与输入文件相同的路径但添加.encrypted后缀
    set OUTPUT_FILE=%INPUT_FILE%.encrypted
)

echo 警告: 此工具将对配置文件中的所有文本内容进行加密！
echo 超长文本将自动使用分段加密（每段约20个字符）。
echo.
echo 输入文件: %INPUT_FILE%
echo 输出文件: %OUTPUT_FILE%
echo 原始备份: %INPUT_FILE%.original
echo.
set /p confirm=是否继续? (Y/N): 

if /i "%confirm%" NEQ "Y" (
    echo 操作已取消.
    pause
    exit /b 0
)

set FORCE_OPTION=--force
echo 已默认启用强制模式。

set SKIP_OPTION=
set /p skip_confirm=是否跳过已包含加密内容的文件？ (Y/N): 
if /i "%skip_confirm%" EQU "Y" (
    set SKIP_OPTION=--skip-encrypted
    echo 已启用跳过已加密文件选项。
)

REM 运行加密脚本
D:\Python\python encrypt_all_text.py %FORCE_OPTION% %SKIP_OPTION% "%INPUT_FILE%" "%OUTPUT_FILE%"

if %errorlevel% neq 0 (
    echo 配置文件加密失败！
    pause
) else (
    echo.
    echo 加密完成！超长文本已使用分段加密（每段约20个字符）。
    echo 原始文件备份: %INPUT_FILE%.original
    echo 加密后文件: %OUTPUT_FILE%
    if "%OUTPUT_FILE%"=="config.yaml" echo 备份用于验证的文件: config.backup.yaml
    echo.
    echo 您现在可以使用加密后的配置文件了。
    pause
) 