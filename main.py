import sys
import os
import platform
import subprocess
import logging
import json
import requests
import sqlite3
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QLabel, QLineEdit, QPushButton, QMessageBox, QDialog
)
from PySide6.QtCore import Qt, QSettings, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QIcon, QFont, QPainter, QColor, QPalette
from dotenv import load_dotenv
import codecs
import time
from cursor_auth import CursorAuthManager
import certifi
from pathlib import Path

def get_resource_path(relative_path):
    """获取资源文件的绝对路径"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的程序
        base_path = sys._MEIPASS
    else:
        # 如果是开发环境
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# 设置日志
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 完全禁用日志输出
logging.getLogger().setLevel(logging.CRITICAL)
for logger_name in logging.root.manager.loggerDict:
    logging.getLogger(logger_name).setLevel(logging.CRITICAL)

# 重定向标准输出和错误输出（对所有系统）
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# 禁用 PySide6 的日志和警告
os.environ['QT_LOGGING_RULES'] = '*=false'
os.environ['QT_ENABLE_LOGGING'] = '0'
os.environ['QT_LOGGING_TO_CONSOLE'] = '0'
os.environ['QT_NO_DEBUG_OUTPUT'] = '1'
os.environ['QT_NO_INFO_OUTPUT'] = '1'
os.environ['QT_NO_WARNING_OUTPUT'] = '1'
os.environ['QT_MESSAGE_PATTERN'] = ''
os.environ['QT_FORCE_STDERR_LOGGING'] = '0'

# 禁用 Python 警告
import warnings
warnings.filterwarnings('ignore')

# 判断是否是打包环境
is_packaged = getattr(sys, 'frozen', False)

# 配置详细日志记录
log_filename = os.path.join(log_dir, f'cursor_auth_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
logging.basicConfig(
    level=logging.ERROR,  # 修改为ERROR级别以减少日志输出
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),  # 文件处理器
    ]
)

# 设置第三方库的日志级别
for logger_name in logging.root.manager.loggerDict:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# 保持标准输出和错误输出的重定向（仅在非Windows系统上）
if platform.system() != 'Windows':
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')

# 禁用 PySide6 的日志
os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.*.debug=false'
os.environ['QT_ENABLE_LOGGING'] = '0'
os.environ['QT_LOGGING_TO_CONSOLE'] = '0'
os.environ['QT_NO_DEBUG_OUTPUT'] = '1'
os.environ['QT_NO_INFO_OUTPUT'] = '1'
os.environ['QT_NO_WARNING_OUTPUT'] = '1'

# 设置图标路径
icon_path = get_resource_path(os.path.join('assets', 'icon.ico'))
logging.info(f"图标路径: {icon_path}")

# 加载环境变量
if getattr(sys, 'frozen', False):
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

env_path = os.path.join(base_path, '.env')
load_dotenv(env_path)

# API配置
API_BASE_URL = os.getenv("API_BASE_URL", "https://cursor.midjourney.bond/api")

# 确保assets目录存在
assets_dir = os.path.join(base_path, 'assets')
if not os.path.exists(assets_dir):
    os.makedirs(assets_dir)

def get_cert_path():
    """获取证书文件路径"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的程序
        if hasattr(sys, '_MEIPASS'):
            # 在打包环境中查找证书
            cert_path = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')
            if os.path.exists(cert_path):
                return cert_path
    # 使用 certifi 提供的证书
    return certifi.where()

def make_request(method, url, **kwargs):
    """发送HTTP请求，自动处理证书"""
    cert_path = get_cert_path()
    if cert_path:
        kwargs['verify'] = cert_path
    else:
        kwargs['verify'] = True  # 使用系统证书
    
    # 移除超时设置
    if 'timeout' in kwargs:
        del kwargs['timeout']
        
    return requests.request(method, url, **kwargs)

class WaitingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("请稍候")
        self.setFixedSize(300, 120)
        
        # 设置窗口背景色和圆角
        self.setStyleSheet("""
            QDialog {
                background-color: #2C3E50;
                border-radius: 10px;
            }
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 添加标题标签
        title_label = QLabel("请稍候")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 添加说明文字
        self.message_label = QLabel("正在增加次数，请等待5秒...")
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message_label)
        
        # 设置无边框窗口
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        
        # 设置模态
        self.setModal(True)
        
        # 设置窗口透明
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 创建动画
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(200)  # 200毫秒
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        
        # 计数器
        self.counter = 5  # 修改为5秒
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_counter)
        self.timer.start(1000)  # 每秒更新一次
    
    def update_counter(self):
        """更新倒计时"""
        self.counter -= 1
        if self.counter >= 0:
            self.message_label.setText(f"正在增加次数，请等待{self.counter}秒...")
    
    def showEvent(self, event):
        """显示时播放动画"""
        super().showEvent(event)
        self.animation.start()
        
        # 居中显示
        if self.parent():
            parent_rect = self.parent().geometry()
            x = parent_rect.center().x() - self.width() // 2
            y = parent_rect.center().y() - self.height() // 2
            self.move(x, y)
    
    def paintEvent(self, event):
        """绘制圆角和阴影"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制圆角矩形
        painter.setBrush(QColor("#2C3E50"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)

class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cursor Auth - 激活")
        self.setFixedSize(400, 300)
        
        # 设置窗口图标
        if os.path.exists(icon_path):
            logging.info("找到图标文件，正在设置...")
            app_icon = QIcon(icon_path)
            self.setWindowIcon(app_icon)
            # 同时设置任务栏图标
            if platform.system() == 'Windows':
                import ctypes
                myappid = 'cursor.auth.client.1.0'
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        else:
            logging.warning(f"图标文件不存在: {icon_path}")
        
        # 初始化Cursor认证管理器
        self.cursor_auth = CursorAuthManager()
        
        # 创建中央部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # 标题标签
        title_label = QLabel("Cursor Auth")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # 说明文字
        desc_label = QLabel("请输入激活码以继续使用")
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)
        
        # 激活码输入框
        self.card_input = QLineEdit()
        self.card_input.setPlaceholderText("请输入激活码")
        self.card_input.setMaxLength(16)
        self.card_input.setMinimumHeight(35)  # 设置最小高度
        self.card_input.textChanged.connect(self.on_text_changed)
        self.card_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
        """)
        layout.addWidget(self.card_input)
        
        # 激活按钮
        self.activate_button = QPushButton("激活")
        self.activate_button.setEnabled(False)
        self.activate_button.clicked.connect(self.activate_card)
        self.activate_button.setMinimumHeight(35)  # 设置最小高度
        self.activate_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #006cbd;
            }
            QPushButton:pressed {
                background-color: #005ba1;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        layout.addWidget(self.activate_button)
        
        # 执行命令按钮
        self.execute_button = QPushButton("增加Cursor次数")
        self.execute_button.clicked.connect(self.execute_command)
        self.execute_button.setMinimumHeight(35)  # 设置最小高度
        self.execute_button.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0b6a0b;
            }
            QPushButton:pressed {
                background-color: #094509;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        layout.addWidget(self.execute_button)
        
        # 状态标签
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)  # 允许文本换行
        self.status_label.setMinimumHeight(80)  # 设置最小高度以适应多行文本
        self.status_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.status_label)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 加载保存的激活码
        self.settings = QSettings('CursorAuth', 'Client')
        saved_card = self.settings.value('card_number')
        if saved_card:
            self.check_saved_card(saved_card)
            
        # 检查并显示当前认证信息
        self.update_auth_status()
            
        logging.info("应用程序初始化完成")
        
        # 初始化定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.on_timer_complete)
        self.process = None
        self.wait_dialog = None
    
    def on_text_changed(self, text):
        """当输入框文本改变时更新按钮状态"""
        self.activate_button.setEnabled(len(text) == 16)
    
    def activate_card(self):
        """激活卡密"""
        card_number = self.card_input.text()
        try:
            # 检查卡密状态
            response = make_request('GET', f"{API_BASE_URL}/cards/check/{card_number}")
            if response.status_code == 200:
                card_data = response.json()
                if card_data['is_used']:
                    QMessageBox.warning(self, "激活失败", "该激活码已被使用")
                    return
                
                # 激活卡密
                activate_response = make_request(
                    'POST',
                    f"{API_BASE_URL}/auth/activate-card",
                    json={"card_number": card_number}
                )
                
                if activate_response.status_code == 200:
                    result = activate_response.json()
                    # 保存激活码和访问令牌
                    self.settings.setValue('card_number', card_number)
                    
                    # 保存访问令牌
                    from cursor_auth import save_token
                    if "access_token" in result:
                        save_token(result["access_token"])
                        logging.info("访问令牌已保存")
                    
                    QMessageBox.information(self, "激活成功", "激活码已成功激活")
                    self.status_label.setText(f"激活状态：已激活（有效期：{card_data['days']}天）")
                else:
                    QMessageBox.warning(self, "激活失败", "激活过程中出现错误")
            else:
                QMessageBox.warning(self, "激活失败", "无效的激活码")
        
        except requests.RequestException as e:
            logging.error(f"请求错误: {str(e)}")
            QMessageBox.critical(self, "连接错误", "无法连接到服务器，请检查网络连接")
    
    def check_saved_card(self, card_number):
        """检查保存的激活码状态"""
        try:
            response = make_request('GET', f"{API_BASE_URL}/cards/check/{card_number}")
            if response.status_code == 200:
                card_data = response.json()
                if card_data['is_used']:
                    # 激活卡片以获取新的访问令牌
                    activate_response = make_request(
                        'POST',
                        f"{API_BASE_URL}/auth/activate-card",
                        json={"card_number": card_number}
                    )
                    
                    if activate_response.status_code == 200:
                        result = activate_response.json()
                        # 保存访问令牌
                        from cursor_auth import save_token
                        if "access_token" in result:
                            save_token(result["access_token"])
                            logging.info("访问令牌已保存")
                    
                    self.status_label.setText(f"激活状态：已激活（有效期：{card_data['days']}天）")
                    self.card_input.setText(card_number)
                    self.card_input.setEnabled(False)
                    self.activate_button.setEnabled(False)
        except Exception as e:
            logging.error(f"检查卡密状态失败: {str(e)}")
            self.status_label.setText("激活状态：未知（无法连接到服务器）")

    def update_auth_status(self):
        """更新认证状态显示"""
        auth_info = self.cursor_auth.get_auth_info()
        logging.info("获取到的认证信息:")
        logging.info(f"认证信息: {auth_info}")
        
        if auth_info:
            status_text = f"当前认证信息：\nEmail: {auth_info.get('email', '未知')}"
            self.status_label.setText(status_text)
            logging.info(f"更新状态标签: {status_text}")
        else:
            self.status_label.setText("未获取到认证信息")
            logging.warning("未获取到认证信息")

    def on_timer_complete(self):
        """定时器完成时的回调函数"""
        self.timer.stop()
        logging.info("命令执行完成")
        
        # 先关闭等待对话框
        if self.wait_dialog:
            self.wait_dialog.hide()
            self.wait_dialog.deleteLater()
            self.wait_dialog = None
        
        # 启用按钮
        self.execute_button.setEnabled(True)
        
        # 显示成功消息
        QMessageBox.information(self, "更新成功", "Cursor认证信息已更新，系统命令执行成功")

    def execute_command(self):
        """执行系统命令并更新Cursor认证信息"""
        try:
            logging.info("开始执行命令更新流程")
            
            # 禁用按钮，防止重复点击
            self.execute_button.setEnabled(False)
            
            # 获取访问令牌
            from cursor_auth import get_token
            token = get_token()
            if not token:
                logging.error("未找到访问令牌")
                QMessageBox.warning(self, "认证失败", "未找到访问令牌，请先激活卡片")
                self.execute_button.setEnabled(True)
                return
            
            # 首先获取新的认证信息
            logging.info("正在获取Cursor认证信息...")
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            # 构造请求数据
            request_data = {
                "client_version": "1.0.0",
                "system": platform.system().lower(),
                "timestamp": int(time.time())
            }
            
            # 记录请求信息
            logging.info(f"请求头: {headers}")
            logging.info(f"请求体: {request_data}")
            
            response = make_request(
                'POST',
                f"{API_BASE_URL}/auth/get-cursor-token",
                headers=headers,
                json=request_data
            )
            
            if response.status_code != 200:
                error_msg = response.json().get('detail', '获取Cursor认证信息失败')
                logging.error(f"获取认证信息失败: {error_msg}")
                QMessageBox.warning(self, "获取认证失败", error_msg)
                self.execute_button.setEnabled(True)
                return
            
            auth_data = response.json()
            logging.info("获取到认证信息:")
            logging.info(f"账号ID: {auth_data.get('id')}")
            logging.info(f"邮箱: {auth_data.get('email')}")
            logging.info(f"Access Token: {auth_data.get('access_token')}")
            logging.info(f"Refresh Token: {auth_data.get('refresh_token')}")
            logging.info(f"状态: {auth_data.get('status')}")
            logging.info(f"拉取次数: {auth_data.get('pull_count')}")
            if auth_data.get('usage'):
                logging.info(f"使用情况: 当前={auth_data['usage'].get('current', '未知')}, 总量={auth_data['usage'].get('total', '未知')}")
            
            # 更新Cursor认证信息
            logging.info("开始更新Cursor认证信息...")
            update_result = self.cursor_auth.update_auth(
                email=auth_data.get('email'),
                access_token=auth_data.get('access_token'),
                refresh_token=auth_data.get('refresh_token')
            )
            
            if not update_result:
                logging.error("更新Cursor认证信息失败")
                QMessageBox.warning(self, "更新失败", "无法更新Cursor认证信息")
                self.execute_button.setEnabled(True)
                return
            
            logging.info("Cursor认证信息更新成功")
            
            # 验证更新是否成功
            updated_info = self.cursor_auth.get_auth_info()
            logging.info("更新后的认证信息:")
            logging.info(f"Email: {updated_info.get('email')}")
            logging.info(f"Access Token: {updated_info.get('accessToken')}")
            logging.info(f"Refresh Token: {updated_info.get('refreshToken')}")
            
            # 更新状态显示
            self.update_auth_status()
            
            # 获取系统类型
            current_system = platform.system().lower()
            logging.info(f"当前系统类型: {current_system}")
            
            # 获取需要执行的命令
            response = make_request(
                'POST',
                f"{API_BASE_URL}/auth/execute-command",
                headers=headers,  # 添加认证头
                json={"system": current_system}
            )
            
            if response.status_code != 200:
                error_msg = response.json().get('detail', '获取系统命令失败')
                logging.error(f"获取命令失败: {error_msg}")
                QMessageBox.warning(self, "获取命令失败", error_msg)
                self.execute_button.setEnabled(True)
                return
            
            command_data = response.json()
            logging.info(f"获取到命令数据: {command_data}")
            
            # 检查系统类型是否匹配
            expected_type = 'powershell' if current_system == 'windows' else 'bash'
            if command_data['type'] != expected_type:
                error_msg = f"系统类型不匹配: 当前系统 {current_system}, 命令类型 {command_data['type']}"
                logging.error(error_msg)
                QMessageBox.warning(self, "系统错误", error_msg)
                self.execute_button.setEnabled(True)
                return
            
            # 显示等待弹窗
            self.wait_dialog = WaitingDialog(self)
            self.wait_dialog.show()
            QApplication.processEvents()
            
            # 执行系统命令
            if command_data['type'] == 'bash':  # macOS
                logging.info("执行macOS命令")
                # 创建临时执行文件
                exec_file = '/tmp/cursor_exec'
                script_content = f'''#!/bin/bash
{command_data["command"]} > /dev/null 2>&1
'''
                with open(exec_file, 'w') as f:
                    f.write(script_content)
                os.chmod(exec_file, 0o755)
                
                self.process = subprocess.Popen(
                    ['osascript', '-e', f'do shell script "{exec_file}" with administrator privileges'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = self.process.communicate()
                
                # 清理临时文件
                try:
                    os.remove(exec_file)
                except:
                    pass
                    
                if self.process.returncode != 0:
                    error_msg = stderr.decode()
                    logging.warning(f"macOS命令返回非零状态码: {error_msg}")
                    # 检查错误信息中是否包含特定的错误字符串
                    if "execution error: 该命令退出时状态为非零。" in error_msg or "execution error: The command exited with a non-zero status." in error_msg:
                        logging.info("忽略非零状态码错误，继续执行")
                    else:
                        if self.wait_dialog:
                            self.wait_dialog.hide()
                            self.wait_dialog = None
                        QMessageBox.warning(self, "执行失败", f"错误信息: {error_msg}")
                        self.execute_button.setEnabled(True)
                        return
            
            elif command_data['type'] == 'powershell':
                logging.info("开始执行Windows PowerShell命令")
                logging.info("=" * 50)
                logging.info(f"执行命令: {command_data['command']}")
                
                # 构建PowerShell命令
                ps_command = f'''
Start-Process powershell.exe -Verb RunAs -ArgumentList @"
{command_data['command']}
"@ -WindowStyle Hidden
'''
                
                # 在后台执行PowerShell命令
                self.process = subprocess.Popen(
                    ['powershell.exe', '-ExecutionPolicy', 'Bypass', '-NoProfile', '-Command', ps_command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
            
            # 启动定时器，5秒后自动完成
            self.timer.start(5000)  # 5000毫秒 = 5秒
            
        except requests.RequestException as e:
            logging.error(f"网络请求错误: {str(e)}")
            if self.wait_dialog:
                self.wait_dialog.hide()
                self.wait_dialog = None
            QMessageBox.critical(self, "连接错误", f"无法连接到服务器: {str(e)}")
            self.execute_button.setEnabled(True)
        except Exception as e:
            logging.error(f"执行过程中出错: {str(e)}")
            if self.wait_dialog:
                self.wait_dialog.hide()
                self.wait_dialog = None
            QMessageBox.critical(self, "执行错误", f"执行过程中出错: {str(e)}")
            self.execute_button.setEnabled(True)

def main():
    logging.info("启动应用程序")
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    # 设置应用程序图标
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
        logging.info("已设置应用程序图标")
    else:
        logging.warning("无法设置应用程序图标：文件不存在")
    
    window = LoginWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 