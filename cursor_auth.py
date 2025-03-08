import os
import sqlite3
import sys
import platform
import requests
import logging
from pathlib import Path
from dotenv import load_dotenv
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def get_base_path():
    """获取基础路径，处理打包后的路径"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的程序
        return os.path.dirname(sys.executable)
    else:
        # 如果是开发环境
        return os.path.dirname(os.path.abspath(__file__))

# 加载环境变量
env_path = os.path.join(get_base_path(), '.env')
load_dotenv(env_path)

# API配置
API_BASE_URL = os.getenv("API_BASE_URL")
if not API_BASE_URL:
    print("警告：未找到API_BASE_URL配置，使用默认值")
    API_BASE_URL = "https://cursor-s.qaqgpt.com/api"

def get_token():
    """获取认证token"""
    token_path = Path.home() / ".cursor_auth" / "token"
    if token_path.exists():
        return token_path.read_text().strip()
    return None

def save_token(token):
    """保存认证token"""
    token_dir = Path.home() / ".cursor_auth"
    token_dir.mkdir(parents=True, exist_ok=True)
    token_path = token_dir / "token"
    token_path.write_text(token)

def clear_auth_info():
    """清理所有认证信息"""
    try:
        # 清理 token 文件
        token_path = Path.home() / ".cursor_auth" / "token"
        if token_path.exists():
            token_path.unlink()
        
        # 清理数据库中的认证信息
        auth_manager = CursorAuthManager()
        conn = None
        try:
            conn = sqlite3.connect(auth_manager.db_path)
            cursor = conn.cursor()
            
            # 删除所有认证相关的记录
            cursor.execute("""
                DELETE FROM itemTable 
                WHERE key LIKE 'cursorAuth/%'
            """)
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"清理数据库认证信息失败: {str(e)}")
            return False
        finally:
            if conn:
                conn.close()
    except Exception as e:
        print(f"清理认证信息失败: {str(e)}")
        return False

def activate_card(card_number):
    """激活卡片"""
    try:
        # 先清理旧的认证信息
        clear_auth_info()
        
        response = requests.post(
            f"{API_BASE_URL}/auth/activate-card",
            json={"card_number": card_number}
        )
        response.raise_for_status()
        result = response.json()
        
        # 保存访问令牌
        if "access_token" in result:
            save_token(result["access_token"])
            print("访问令牌已保存")
        
        return result
    except requests.exceptions.RequestException as e:
        print(f"激活卡片失败: {str(e)}")
        return None

class CursorAuthManager:
    """Cursor认证信息管理器"""

    def __init__(self):
        # 判断操作系统
        if platform.system() == "Windows":  # Windows
            appdata = os.getenv("APPDATA")
            if appdata is None:
                raise EnvironmentError("APPDATA 环境变量未设置")
            cursor_dir = os.path.join(appdata, "Cursor", "User", "globalStorage")
            self.db_path = os.path.join(cursor_dir, "state.vscdb")
            # 确保目录存在
            os.makedirs(cursor_dir, exist_ok=True)
        elif platform.system() == "Darwin":  # macOS
            cursor_dir = os.path.expanduser("~/Library/Application Support/Cursor/User/globalStorage")
            self.db_path = os.path.join(cursor_dir, "state.vscdb")
            # 确保目录存在
            os.makedirs(cursor_dir, exist_ok=True)
        elif platform.system() == "Linux":  # Linux
            cursor_dir = os.path.expanduser("~/.config/Cursor/User/globalStorage")
            self.db_path = os.path.join(cursor_dir, "state.vscdb")
            # 确保目录存在
            os.makedirs(cursor_dir, exist_ok=True)
        else:
            raise NotImplementedError(f"不支持的操作系统: {platform.system()}")
            
        # 初始化数据库
        self._init_database()

    def _init_database(self):
        """初始化数据库表结构"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建表（如果不存在）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS itemTable (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            conn.commit()
        except sqlite3.Error as e:
            print(f"初始化数据库错误: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def update_auth(self, email=None, access_token=None, refresh_token=None):
        """
        更新Cursor的认证信息
        :param email: 新的邮箱地址
        :param access_token: 新的访问令牌
        :param refresh_token: 新的刷新令牌
        :return: bool 是否成功更新
        """
        try:
            updates = []
            # 登录状态 - 使用 cachedSignUpType 而不是 signUpType
            updates.append(("cursorAuth/cachedSignUpType", "Auth_0"))
            updates.append(("cursorAuth/signUpType", "Auth_0"))
            updates.append(("cursorAuth/isLoggedIn", "true"))  # 添加登录状态
            updates.append(("cursorAuth/stripeMembershipType", "free_trial"))  # 添加会员类型
            
            if email is not None:
                # 使用 cachedEmail 而不是 email
                updates.append(("cursorAuth/cachedEmail", email))
                updates.append(("cursorAuth/email", email))  # 同时更新 email
                logging.info(f"准备更新邮箱: {email}")
            
            if refresh_token and refresh_token.startswith("ey"):
                # 使用refresh_token作为所有token
                jwt_token = refresh_token
                
                # 存储 JWT 格式的 token
                updates.append(("cursorAuth/cachedAccessToken", jwt_token))
                updates.append(("cursorAuth/accessToken", jwt_token))
                updates.append(("cursorAuth/token", jwt_token))
                updates.append(("cursorAuth/refreshToken", jwt_token))
                updates.append(("cursorAuth/cachedRefreshToken", jwt_token))
                logging.info("准备更新访问令牌和刷新令牌")
            
            # 更新数据库
            conn = None
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # 确保表存在
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS itemTable (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                
                logging.info("开始更新数据库...")
                for key, value in updates:
                    # 检查键是否存在
                    cursor.execute("SELECT COUNT(*) FROM itemTable WHERE key = ?", (key,))
                    if cursor.fetchone()[0] == 0:
                        # 如果键不存在，执行插入
                        cursor.execute("""
                            INSERT INTO itemTable (key, value)
                            VALUES (?, ?)
                        """, (key, value))
                    else:
                        # 如果键存在，执行更新
                        cursor.execute("""
                            UPDATE itemTable SET value = ? WHERE key = ?
                        """, (value, key))
                    
                    if cursor.rowcount > 0:
                        logging.info(f"成功更新 {key.split('/')[-1]}")
                    else:
                        logging.info(f"未找到 {key.split('/')[-1]} 或值未变化")
                
                conn.commit()
                logging.info("数据库更新成功")
                
                # 验证更新
                cursor.execute("SELECT key, value FROM itemTable WHERE key LIKE 'cursorAuth/%'")
                results = cursor.fetchall()
                logging.info("更新后的数据库内容:")
                for key, value in results:
                    # 不打印敏感信息
                    if 'token' in key.lower():
                        logging.info(f"{key}: ******")
                    else:
                        logging.info(f"{key}: {value}")
                
                return True
            except sqlite3.Error as e:
                logging.error(f"更新数据库错误: {e}")
                return False
            finally:
                if conn:
                    conn.close()
        except Exception as e:
            logging.error(f"更新认证信息失败: {str(e)}")
            return False

    def get_auth_info(self):
        """
        获取当前的认证信息
        :return: dict 包含email、access_token和refresh_token的字典
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询所有认证相关的键
            cursor.execute("""
                SELECT key, value FROM itemTable 
                WHERE key LIKE 'cursorAuth/%'
            """)
            
            result = {}
            for key, value in cursor.fetchall():
                field = key.split('/')[-1]
                result[field] = value
            
            # 确保返回必要的字段
            if 'email' not in result:
                result['email'] = '未知'
            if 'accessToken' not in result:
                result['accessToken'] = None
            if 'refreshToken' not in result:
                result['refreshToken'] = None
            
            return result
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
            return {'email': '未知', 'accessToken': None, 'refreshToken': None}
        finally:
            if conn:
                conn.close()

def update_cursor_auth(email=None, access_token=None, refresh_token=None):
    """更新Cursor的认证信息"""
    try:
        # 获取访问令牌
        token = get_token()
        if not token:
            logging.warning("未找到访问令牌，请先激活卡片")
            return False
        
        # 清理旧的认证信息
        clear_auth_info()
        
        # 从服务器获取新的token
        max_retries = 3  # 最大重试次数
        for attempt in range(max_retries):
            logging.info(f"\n尝试第 {attempt + 1} 次获取账号")
            try:
                # 添加请求体
                request_data = {
                    "client_version": "1.0.0",
                    "system": platform.system().lower(),
                    "timestamp": int(time.time())
                }
                
                response = requests.post(
                    f"{API_BASE_URL}/auth/get-cursor-token",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    json=request_data
                )
                
                # 详细记录请求信息
                logging.info(f"请求URL: {response.url}")
                logging.info(f"请求头: {response.request.headers}")
                logging.info(f"请求体: {request_data}")
                logging.info(f"响应状态码: {response.status_code}")
                
                response.raise_for_status()
                data = response.json()
                
                # 检查响应数据
                if not isinstance(data, dict):
                    raise ValueError("服务器返回数据格式错误")
                    
                # 使用服务器返回的信息
                email = data.get("email")
                password = data.get("password")  # 获取密码
                refresh_token = data.get("refresh_token")  # 获取真实的refresh_token
                status = data.get("status")
                pull_count = data.get("pull_count", 0)
                usage = data.get("usage", {})
                
                # 使用refresh_token作为access_token
                if refresh_token and refresh_token.startswith("ey"):
                    access_token = refresh_token
                else:
                    # 如果没有有效的refresh_token，尝试获取
                    try:
                        refresh_response = requests.post(
                            f"{API_BASE_URL}/auth/get-refresh-token",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"email": email, "password": password}
                        )
                        refresh_response.raise_for_status()
                        refresh_data = refresh_response.json()
                        refresh_token = refresh_data.get("refresh_token")
                        if refresh_token and refresh_token.startswith("ey"):
                            access_token = refresh_token
                        else:
                            logging.error("获取到的refresh_token格式不正确")
                            continue
                    except Exception as e:
                        logging.error(f"获取refresh_token失败: {str(e)}")
                        continue
                
                logging.info("\n获取到的账号信息:")
                logging.info(f"账号ID: {data.get('id')}")
                logging.info(f"邮箱: {email}")
                logging.info(f"状态: {status}")
                logging.info(f"拉取次数: {pull_count}")
                if usage:
                    logging.info(f"使用情况: 当前={usage.get('current', '未知')}, 总量={usage.get('total', '未知')}")
                
                # 检查账号是否可用
                if status in ["EXCEEDED", "DEPLETED"] or pull_count >= 5:
                    logging.warning(f"\n账号不可用: status={status}, pull_count={pull_count}")
                    if attempt < max_retries - 1:
                        logging.info("尝试获取下一个账号...")
                        continue
                    else:
                        logging.error("已达到最大重试次数，无法获取可用账号")
                        return False
                    
                if not all([email, access_token, refresh_token]):
                    logging.warning("\n账号信息不完整，尝试获取下一个账号...")
                    continue
                
                # 更新本地认证信息
                auth_manager = CursorAuthManager()
                success = auth_manager.update_auth(
                    email=email,
                    access_token=access_token,
                    refresh_token=refresh_token
                )
                
                if success:
                    logging.info("\n成功更新认证信息")
                    logging.info(f"邮箱: {email}")
                    if usage:
                        logging.info(f"账号使用情况: 当前={usage.get('current', '未知')}, 总量={usage.get('total', '未知')}")
                    return True
                else:
                    logging.error("\n更新认证信息失败")
                    if attempt < max_retries - 1:
                        logging.info("尝试获取下一个账号...")
                        continue
                
            except requests.RequestException as e:
                logging.error(f"\n请求服务器失败: {str(e)}")
                if attempt < max_retries - 1:
                    continue
                return False
                    
        logging.error("\n无法获取可用账号")
        return False
        
    except Exception as e:
        logging.error(f"\n更新认证信息失败: {str(e)}")
        return False 