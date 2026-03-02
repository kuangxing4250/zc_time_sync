# -*- coding: utf-8 -*-
# 时间同步助手 - 主程序
# 功能：设置开机自启动、定时任务、配置管理
# 作者：zgric团队
# 版本：v0.0.3-beta.0

import os
import sys
import json
import ctypes
import logging
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    from tkinter import *
    from tkinter import messagebox, ttk
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

APP_NAME = "ZGIRC时间同步"
VERSION = "0.0.3"
EXE_NAME = "ZGIRC_TimeSync.exe"
TIME_SYNC_SCRIPT = "time_sync.py"

# 判断是否为打包后的程序
if getattr(sys, 'frozen', False):
    SCRIPT_DIR = Path(sys.executable).parent.resolve()
else:
    SCRIPT_DIR = Path(__file__).parent.resolve()

DATA_DIR = SCRIPT_DIR / "data"
CONFIG_FILE = DATA_DIR / "config.json"
TIME_SYNC_EXE = DATA_DIR / "time_sync.exe"
LOG_DIR = SCRIPT_DIR / "log"
LOG_FILE = LOG_DIR / f"main_{datetime.now().strftime('%Y%m%d')}.log"

def setup_logging():
    """设置日志系统"""
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

def clean_old_logs(log_dir, days=7):
    """
    清理过期的日志文件
    参数:
        log_dir: 日志目录路径
        days: 保留天数，默认7天
    返回: 清理的日志数量
    """
    if not log_dir.exists():
        return 0
    
    cleaned_count = 0
    now = datetime.now()
    
    for log_file in log_dir.glob("*.log"):
        try:
            # 获取文件修改时间
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
            # 如果文件超过指定天数，则删除
            if (now - mtime).days > days:
                log_file.unlink()
                cleaned_count += 1
                logging.debug(f"已清理过期日志: {log_file.name}")
        except Exception as e:
            logging.warning(f"清理日志失败 {log_file.name}: {e}")
    
    return cleaned_count

def load_config():
    """加载配置文件"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            pass
    
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
        "retry_count": 3,
        "sync_interval": 3600,
        "log_days": 7  # 日志保留天数
    }

def save_config(config):
    """保存配置文件到文件"""
    try:
        CONFIG_FILE.parent.mkdir(exist_ok=True, parents=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logging.debug(f"配置已保存: {config}")
        return True
    except Exception as e:
        logging.error(f"保存配置文件失败: {e}")
        return False

def is_admin():
    """检查是否具有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def get_startup_path():
    """获取开机自启动的注册表路径"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, 
            r"Software\Microsoft\Windows\CurrentVersion\Run", 
            0, 
            winreg.KEY_READ
        )
        try:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            logging.debug(f"找到开机自启动配置: {value}")
            return value
        except FileNotFoundError:
            logging.debug("未找到开机自启动配置")
            return None
    except Exception as e:
        logging.error(f"读取开机启动项失败: {e}")
        return None

def set_startup(enable):
    """
    设置开机自启动 - 自动运行时间同步程序
    参数:
        enable: True=启用，False=禁用
    返回: True=成功，False=失败
    """
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, 
            r"Software\Microsoft\Windows\CurrentVersion\Run", 
            0, 
            winreg.KEY_WRITE
        )
        
        if enable:
            # 开机自启动运行时间同步程序
            exe_path = sys.executable
            # 优先使用exe（打包后），其次使用py（开发时）
            script_name_py = "time_sync.py"
            script_name_exe = "time_sync.exe"
            
            script_path = DATA_DIR / script_name_exe
            if not script_path.exists():
                script_path = DATA_DIR / script_name_py
            
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}" "{script_path}"')
            logging.info(f"已设置开机自启动: {exe_path} {script_path}")
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
                logging.info("已移除开机自启动")
            except FileNotFoundError:
                pass
        
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logging.error(f"设置开机自启动失败: {e}")
        return False

def check_startup_enabled():
    """检查开机自启动是否已启用"""
    return get_startup_path() is not None

def create_scheduled_task(task_name, interval_minutes):
    """
    创建Windows定时任务
    参数:
        task_name: 任务名称
        interval_minutes: 间隔分钟数
    返回: True=成功，False=失败
    """
    try:
        exe_path = sys.executable
        # 使用schtasks命令创建定时任务
        task_cmd = f'schtasks /create /tn "{task_name}" /tr "\\"{exe_path}\\" --sync" /sc minute /mo {interval_minutes} /f'
        logging.debug(f"创建定时任务命令: {task_cmd}")
        
        result = subprocess.run(task_cmd, shell=True, capture_output=True, text=True)
        logging.debug(f"创建定时任务结果: returncode={result.returncode}, stdout={result.stdout}, stderr={result.stderr}")
        
        return result.returncode == 0
    except Exception as e:
        logging.error(f"创建定时任务异常: {e}")
        return False

def delete_scheduled_task(task_name):
    """
    删除Windows定时任务
    参数:
        task_name: 任务名称
    返回: True=成功，False=失败
    """
    try:
        task_cmd = f'schtasks /delete /tn "{task_name}" /f'
        logging.debug(f"删除定时任务命令: {task_cmd}")
        
        result = subprocess.run(task_cmd, shell=True, capture_output=True, text=True)
        logging.debug(f"删除定时任务结果: returncode={result.returncode}, stdout={result.stdout}, stderr={result.stderr}")
        
        return result.returncode == 0
    except Exception as e:
        logging.error(f"删除定时任务异常: {e}")
        return False

def check_scheduled_task_exists(task_name):
    """
    检查定时任务是否存在
    参数:
        task_name: 任务名称
    返回: True=存在，False=不存在
    """
    try:
        task_cmd = f'schtasks /query /tn "{task_name}"'
        result = subprocess.run(task_cmd, shell=True, capture_output=True, text=True)
        logging.debug(f"检查定时任务结果: returncode={result.returncode}")
        return result.returncode == 0
    except Exception as e:
        logging.error(f"检查定时任务异常: {e}")
        return False

def run_time_sync():
    """
    运行时间同步程序
    返回: (成功标志, 消息)
    """
    # 优先使用exe（打包后），其次使用py（开发时）
    script_name_py = "time_sync.py"
    script_name_exe = "time_sync.exe"
    
    script_path = DATA_DIR / script_name_exe
    if not script_path.exists():
        script_path = DATA_DIR / script_name_py
        if not script_path.exists():
            logging.error(f"时间同步脚本不存在: {script_path}")
            return False, "时间同步脚本不存在"
    
    try:
        # 打包后直接运行exe，开发模式用python运行
        if getattr(sys, 'frozen', False):
            # 打包后直接运行time_sync.exe
            exe_path = str(script_path)
            logging.debug(f"执行时间同步(直接运行exe): {exe_path}")
            
            result = subprocess.run(
                [exe_path],
                capture_output=True,
                text=True,
                timeout=30
            )
        else:
            # 开发模式用python运行
            python_exe = sys.executable
            logging.debug(f"执行时间同步: {python_exe} {script_path}")
            
            result = subprocess.run(
                [python_exe, str(script_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
        
        logging.debug(f"时间同步返回码: {result.returncode}")
        logging.debug(f"时间同步输出: stdout={result.stdout}, stderr={result.stderr}")
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except Exception as e:
        logging.error(f"运行时间同步程序异常: {e}")
        return False, str(e)

class TimeSyncApp:
    """主程序GUI类 - 处理用户界面和交互"""
    
    def __init__(self, root):
        """
        初始化GUI
        参数:
            root: Tk窗口对象
        """
        self.root = root
        self.root.title(f"{APP_NAME} v{VERSION}")
        self.root.geometry("450x580")
        self.root.resizable(False, False)
        
        # 初始化日志系统
        self.logger = setup_logging()
        self.logger.info("=" * 50)
        self.logger.info("主程序启动")
        
        # 加载配置
        self.config = load_config()
        
        # 启动时清理过期日志
        log_days = self.config.get("log_days", 7)
        cleaned = clean_old_logs(LOG_DIR, log_days)
        if cleaned > 0:
            self.logger.info(f"已清理 {cleaned} 个过期日志文件")
        
        self.sync_thread = None
        self.scheduled_sync_thread = None
        self.stop_scheduled = False
        
        # 创建GUI组件
        self.create_widgets()
        # 检查管理员权限
        self.check_and_show_admin()
        
        # 处理命令行参数
        if "--sync" in sys.argv:
            # 定时任务触发，隐藏窗口
            self.root.withdraw()
            self.run_sync_and_exit()
        elif "--hidden" in sys.argv:
            # 开机启动，隐藏窗口
            self.root.withdraw()
    
    def create_widgets(self):
        """创建GUI组件"""
        main_frame = Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=BOTH, expand=True)
        
        # 标题
        title_label = Label(main_frame, text="时间同步助手", font=("微软雅黑", 18, "bold"))
        title_label.pack(pady=10)
        
        # 状态显示区域
        status_frame = LabelFrame(main_frame, text="状态", font=("微软雅黑", 10))
        status_frame.pack(fill=X, pady=10)
        
        self.admin_label = Label(status_frame, text="管理员权限: 未检测", fg="gray")
        self.admin_label.pack(anchor=W, padx=10, pady=5)
        
        self.startup_label = Label(status_frame, text="开机自启动: 未启用", fg="gray")
        self.startup_label.pack(anchor=W, padx=10, pady=5)
        
        self.task_label = Label(status_frame, text="定时同步: 未启用", fg="gray")
        self.task_label.pack(anchor=W, padx=10, pady=5)
        
        # 初始化复选框变量
        self.startup_var = BooleanVar(value=check_startup_enabled())
        self.scheduled_var = BooleanVar(value=check_scheduled_task_exists(APP_NAME + "_Sync"))
        
        # 更新状态显示
        self.update_status()
        
        # 配置区域
        config_frame = LabelFrame(main_frame, text="配置", font=("微软雅黑", 10))
        config_frame.pack(fill=X, pady=10)
        
        # 时区偏移设置
        time_offset_frame = Frame(config_frame)
        time_offset_frame.pack(fill=X, padx=10, pady=5)
        Label(time_offset_frame, text="时区偏移(小时):").pack(side=LEFT)
        self.time_offset_var = IntVar(value=self.config.get("time_offset", 8))
        Spinbox(time_offset_frame, from_=-12, to=12, textvariable=self.time_offset_var, width=10).pack(side=LEFT, padx=10)
        
        # 同步间隔设置
        interval_frame = Frame(config_frame)
        interval_frame.pack(fill=X, padx=10, pady=5)
        Label(interval_frame, text="同步间隔(分钟):").pack(side=LEFT)
        self.interval_var = IntVar(value=self.config.get("sync_interval", 60) // 60)
        Spinbox(interval_frame, from_=1, to=1440, textvariable=self.interval_var, width=10).pack(side=LEFT, padx=10)
        
        # 日志保留天数设置
        log_days_frame = Frame(config_frame)
        log_days_frame.pack(fill=X, padx=10, pady=5)
        Label(log_days_frame, text="日志保留(天):").pack(side=LEFT)
        self.log_days_var = IntVar(value=self.config.get("log_days", 7))
        Spinbox(log_days_frame, from_=1, to=30, textvariable=self.log_days_var, width=10).pack(side=LEFT, padx=10)
        
        # 按钮区域
        button_frame = Frame(main_frame)
        button_frame.pack(pady=15)
        
        Button(button_frame, text="立即同步时间", command=self.sync_now, width=15, height=2).pack(side=LEFT, padx=5)
        Button(button_frame, text="保存配置", command=self.save_settings, width=15, height=2).pack(side=LEFT, padx=5)
        
        # 选项区域
        options_frame = LabelFrame(main_frame, text="选项", font=("微软雅黑", 10))
        options_frame.pack(fill=X, pady=10)
        
        Checkbutton(options_frame, text="开机自动启动", variable=self.startup_var, command=self.toggle_startup).pack(anchor=W, padx=10, pady=5)
        
        Checkbutton(options_frame, text="定时自动同步", variable=self.scheduled_var, command=self.toggle_scheduled).pack(anchor=W, padx=10, pady=5)
        
        # 工具按钮区域
        tools_frame = Frame(main_frame)
        tools_frame.pack(fill=X, pady=5)
        
        Button(tools_frame, text="清理日志", command=self.clean_logs, width=15).pack(side=LEFT, padx=5)
        
        # 日志显示区域
        log_frame = LabelFrame(main_frame, text="日志", font=("微软雅黑", 10))
        log_frame.pack(fill=BOTH, expand=True, pady=10)
        
        self.log_text = Text(log_frame, height=6, state=DISABLED)
        self.log_text.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = Scrollbar(self.log_text)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.log_text.yview)
    
    def update_status(self):
        """更新状态显示"""
        # 检查管理员权限
        if is_admin():
            self.admin_label.config(text="管理员权限: 已获得", fg="green")
        else:
            self.admin_label.config(text="管理员权限: 未获得(部分功能受限)", fg="red")
        
        # 检查开机自启动状态
        if check_startup_enabled():
            self.startup_label.config(text="开机自启动: 已启用", fg="green")
            self.startup_var.set(True)
        else:
            self.startup_label.config(text="开机自启动: 未启用", fg="gray")
            self.startup_var.set(False)
        
        # 检查定时任务状态
        if check_scheduled_task_exists(APP_NAME + "_Sync"):
            self.task_label.config(text="定时同步: 已启用", fg="green")
            self.scheduled_var.set(True)
        else:
            self.task_label.config(text="定时同步: 未启用", fg="gray")
            self.scheduled_var.set(False)
    
    def check_and_show_admin(self):
        """检查并提示管理员权限"""
        if not is_admin():
            messagebox.showwarning("提示", "建议以管理员身份运行以启用完整功能")
    
    def add_log(self, message):
        """
        添加日志到显示区域
        参数:
            message: 日志消息
        """
        self.log_text.config(state=NORMAL)
        self.log_text.insert(END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.log_text.see(END)
        self.log_text.config(state=DISABLED)
        self.logger.info(message)
    
    def sync_now(self):
        """立即同步时间"""
        def do_sync():
            self.add_log("开始同步时间...")
            success, message = run_time_sync()
            if success:
                self.add_log(f"同步成功: {message.strip()}")
                messagebox.showinfo("成功", "时间同步成功!")
            else:
                self.add_log(f"同步失败: {message.strip()}")
                messagebox.showerror("失败", f"时间同步失败:\n{message}")
        
        # 在新线程中执行，避免阻塞GUI
        thread = threading.Thread(target=do_sync)
        thread.daemon = True
        thread.start()
    
    def save_settings(self):
        """保存配置"""
        self.config["time_offset"] = self.time_offset_var.get()
        self.config["sync_interval"] = self.interval_var.get() * 60
        self.config["log_days"] = self.log_days_var.get()
        
        if save_config(self.config):
            self.add_log("配置已保存")
            messagebox.showinfo("成功", "配置已保存")
        else:
            self.add_log("配置保存失败")
            messagebox.showerror("失败", "配置保存失败")
    
    def toggle_startup(self):
        """切换开机自启动"""
        enable = self.startup_var.get()
        if set_startup(enable):
            self.add_log(f"开机自启动已{'启用' if enable else '禁用'}")
            self.update_status()
        else:
            self.startup_var.set(not enable)
            messagebox.showerror("失败", "设置开机自启动失败")
    
    def toggle_scheduled(self):
        """切换定时同步"""
        enable = self.scheduled_var.get()
        interval = self.interval_var.get()
        
        if enable:
            if create_scheduled_task(APP_NAME + "_Sync", interval):
                self.add_log(f"定时同步已启用 (每{interval}分钟)")
                self.update_status()
            else:
                self.scheduled_var.set(False)
                messagebox.showerror("失败", "创建定时任务失败")
        else:
            if delete_scheduled_task(APP_NAME + "_Sync"):
                self.add_log("定时同步已禁用")
                self.update_status()
            else:
                self.scheduled_var.set(True)
                messagebox.showerror("失败", "删除定时任务失败")
    
    def clean_logs(self):
        """清理过期日志"""
        days = self.log_days_var.get()
        cleaned = clean_old_logs(LOG_DIR, days)
        self.add_log(f"已清理 {cleaned} 个过期日志文件 (保留{days}天)")
        messagebox.showinfo("完成", f"已清理 {cleaned} 个过期日志文件")
    
    def run_sync_and_exit(self):
        """运行同步并退出 (用于定时任务或开机启动)"""
        time.sleep(2)
        success, message = run_time_sync()
        if success:
            self.logger.info(f"时间同步成功: {message}")
        else:
            self.logger.error(f"时间同步失败: {message}")
        self.root.destroy()
        sys.exit(0 if success else 1)
    
    def run(self):
        """运行程序"""
        self.root.mainloop()

def main():
    """主函数"""
    if not HAS_TKINTER:
        print("错误: 需要安装tkinter库")
        print("请使用: pip install tkinter")
        sys.exit(1)
    
    if "--sync" in sys.argv:
        logger = setup_logging()
        logger.info("定时任务触发时间同步")
        success, message = run_time_sync()
        if success:
            print(f"时间同步成功: {message}")
        else:
            print(f"时间同步失败: {message}")
        sys.exit(0 if success else 1)
    
    root = Tk()
    app = TimeSyncApp(root)
    app.run()

if __name__ == "__main__":
    main()
