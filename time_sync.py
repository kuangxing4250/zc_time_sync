# -*- coding: utf-8 -*-
# 时间同步程序
# 功能：从NTP服务器获取时间并设置系统时间
# 作者：zgric团队
# 版本：v0.0.3-beta.0

import os
import sys
import json
import time
import struct
import socket
import ctypes
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path

APP_NAME = "ZGIRC时间同步"
VERSION = "0.0.3"

# 判断是否为打包后的程序
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = Path(sys.executable).parent.resolve()
else:
    SCRIPT_DIR = Path(__file__).parent.resolve()

DATA_DIR = SCRIPT_DIR / "data"
CONFIG_FILE = DATA_DIR / "config.json"
LOG_DIR = SCRIPT_DIR / "log"
LOG_FILE = LOG_DIR / f"time_sync_{datetime.now().strftime('%Y%m%d')}.log"

# NTP协议使用的Unix纪元时间偏移
NTP_EPOCH = 2208988800

def setup_logging():
    """
    设置日志系统
    返回: logger对象
    """
    LOG_DIR.mkdir(exist_ok=True, parents=True)
    
    # 设置日志级别为DEBUG，记录更详细的信息
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def load_config():
    """
    加载配置文件
    返回: 配置字典
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logging.debug(f"已加载配置: {config}")
                return config
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
    
    # 默认配置
    return {
        "ntp_servers": [
            "time1.aliyun.com",
            "time2.aliyun.com",
            "time3.aliyun.com",
            "time4.aliyun.com",
            "pool.ntp.org"
        ],
        "time_offset": 8,
        "retry_count": 3
    }

def save_config(config):
    """
    保存配置文件
    参数:
        config: 配置字典
    返回: True=成功，False=失败
    """
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logging.debug(f"配置已保存: {config}")
        return True
    except Exception as e:
        logging.error(f"保存配置失败: {e}")
        return False

def is_admin():
    """
    检查是否具有管理员权限
    返回: True=有管理员权限，False=没有
    """
    try:
        result = ctypes.windll.shell32.IsUserAnAdmin()
        logging.debug(f"管理员权限检查结果: {result}")
        return result
    except Exception as e:
        logging.error(f"检查管理员权限失败: {e}")
        return False

def set_system_time(year, month, day, hour, minute, second):
    """
    设置系统时间
    参数:
        year, month, day, hour, minute, second: 时间组成部分
    返回: (成功标志, 消息)
    """
    try:
        dt = datetime(year, month, day, hour, minute, second)
        logging.debug(f"准备设置系统时间: {dt}")
        
        # 使用Windows的date和time命令设置时间
        date_cmd = f'date {dt.strftime("%Y-%m-%d")}'
        time_cmd = f'time {dt.strftime("%H:%M:%S")}'
        
        logging.debug(f"执行命令: {date_cmd}")
        date_result = subprocess.run(date_cmd, shell=True, capture_output=True, text=True)
        logging.debug(f"date命令结果: returncode={date_result.returncode}")
        
        logging.debug(f"执行命令: {time_cmd}")
        time_result = subprocess.run(time_cmd, shell=True, capture_output=True, text=True)
        logging.debug(f"time命令结果: returncode={time_result.returncode}")
        
        return True, "时间设置成功"
    except Exception as e:
        logging.error(f"设置系统时间失败: {e}")
        return False, f"设置时间失败: {e}"

def get_ntp_time(server, timeout=5):
    """
    从NTP服务器获取时间
    参数:
        server: NTP服务器地址
        timeout: 超时时间（秒）
    返回: (成功标志, datetime对象或错误信息)
    """
    try:
        logging.debug(f"连接到NTP服务器: {server}")
        socket.setdefaulttimeout(timeout)
        
        # 创建UDP客户端
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # 发送NTP请求 (mode 3 = client)
        client.sendto(b'\x1b' + 47 * b'\0', (server, 123))
        
        # 接收响应
        data, addr = client.recvfrom(1024)
        client.close()
        
        logging.debug(f"从 {addr} 收到NTP响应")
        
        # 解析NTP时间戳 (第11个32位整数)
        ntp_time = struct.unpack('!12I', data)[10]
        
        # 转换为Unix时间戳
        ntp_time -= NTP_EPOCH
        
        # 转换为datetime对象
        result_time = datetime.fromtimestamp(ntp_time)
        logging.debug(f"NTP时间: {result_time}")
        
        return True, result_time
    except socket.timeout:
        logging.warning(f"NTP服务器 {server} 连接超时")
        return False, "连接超时"
    except socket.error as e:
        logging.warning(f"NTP服务器 {server} 连接错误: {e}")
        return False, str(e)
    except Exception as e:
        logging.warning(f"获取NTP时间失败 {server}: {e}")
        return False, str(e)

def sync_time(config, logger):
    """
    同步系统时间
    参数:
        config: 配置字典
        logger: 日志对象
    返回: (成功标志, 消息)
    """
    ntp_servers = config.get("ntp_servers", [])
    time_offset = config.get("time_offset", 8)
    retry_count = config.get("retry_count", 3)
    
    logger.info(f"时间偏移设置: {time_offset} 小时")
    logger.info(f"重试次数: {retry_count}")
    logger.info(f"NTP服务器列表: {ntp_servers}")
    
    # 检查管理员权限
    if not is_admin():
        logger.error("没有管理员权限，无法设置系统时间")
        return False, "需要管理员权限才能设置系统时间"
    
    last_error = None
    
    # 遍历所有NTP服务器
    for server in ntp_servers:
        logger.info(f"尝试连接服务器: {server}")
        
        for attempt in range(retry_count):
            logger.info(f"尝试从 {server} 获取时间 (尝试 {attempt + 1}/{retry_count})...")
            
            success, result = get_ntp_time(server)
            
            if success:
                target_time = result
                
                # 应用时间偏移
                if time_offset != 0:
                    target_time = target_time + timedelta(hours=time_offset)
                    logger.debug(f"应用时间偏移后: {target_time}")
                
                logger.info(f"获取到的时间: {target_time}")
                
                # 设置系统时间
                success, msg = set_system_time(
                    target_time.year,
                    target_time.month,
                    target_time.day,
                    target_time.hour,
                    target_time.minute,
                    target_time.second
                )
                
                if success:
                    logger.info(f"时间同步成功! 设置为: {target_time}")
                    return True, f"时间同步成功: {target_time}"
                else:
                    last_error = msg
                    logger.error(f"设置时间失败: {msg}")
                    break
            else:
                last_error = result
                logger.warning(f"从 {server} 获取时间失败: {result}")
                # 等待后重试
                time.sleep(1)
    
    logger.error(f"所有NTP服务器同步失败，最后错误: {last_error}")
    return False, f"所有NTP服务器同步失败: {last_error}"

def main():
    """主函数"""
    # 初始化日志
    logger = setup_logging()
    logger.info("=" * 50)
    logger.info(f"时间同步程序启动 (版本 {VERSION})")
    logger.info("=" * 50)
    
    # 加载配置
    config = load_config()
    logger.info(f"当前配置: {config}")
    
    # 执行时间同步
    success, message = sync_time(config, logger)
    
    if success:
        print(f"[OK] {message}")
    else:
        print(f"[X] {message}")
        sys.exit(1)

if __name__ == "__main__":
    main()
