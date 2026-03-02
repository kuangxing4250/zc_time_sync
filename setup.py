# -*- coding: utf-8 -*-
#ZGIRC时间同步 打包配置
#作者：zgric团队
#版本：0.0.3

import os
import sys
import shutil
from pathlib import Path

#要打包的主程序
MAIN_SCRIPT = "main_app.py"
#输出目录
DIST_DIR = "dist"
#程序名称
APP_NAME = "ZGIRC_TimeSync"

def prepare_files():
    """准备需要打包的文件"""
    #创建dist目录
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    os.makedirs(DIST_DIR)
    
    #复制主程序
    shutil.copy(MAIN_SCRIPT, DIST_DIR)
    
    #创建dada目录并复制文件
    dada_dir = os.path.join(DIST_DIR, "dada")
    os.makedirs(dada_dir, exist_ok=True)
    
    #复制time_sync.py
    shutil.copy(os.path.join("dada", "time_sync.py"), dada_dir)
    
    #复制config.json
    if os.path.exists(os.path.join("dada", "config.json")):
        shutil.copy(os.path.join("dada", "config.json"), dada_dir)
    
    print(f"文件准备完成，输出目录: {DIST_DIR}")
    print(f"请使用以下命令打包:")
    print(f"pyinstaller --onefile --windowed --name {APP_NAME} --distpath {DIST_DIR} --workpath build --specpath . {MAIN_SCRIPT}")

if __name__ == "__main__":
    prepare_files()
