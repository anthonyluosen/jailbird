import sys
import os
import traceback

# 使用相对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
trading_platform_path = os.path.join(project_root, "front", "trading_platform")
print(trading_platform_path)
sys.path.append(trading_platform_path)

import redis
import json
import time
from datetime import datetime, timezone, timedelta
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from app.oms.storage import DataStorage
from app.oms.redis_sync import RedisSyncManager
from app.oms.constant import Order, OrderStatus, OrderSide, OrderType
import threading

# Redis配置
REDIS_HOST = '1.95.154.244'
REDIS_PORT = 6379
REDIS_PASSWORD = '123'
REDIS_DB = 0
SYNC_CHANNEL = 'jailbird:sync'
DELETE_CHANNEL = 'jailbird:delete'
ORDERS_HASH = 'jailbird:account:orders'  # 添加订单哈希表的键名

# 本地配置 - 使用相对路径
# 可以通过环境变量或配置文件覆盖
DEFAULT_DB_PATH = os.path.join(project_root, 'trading_data.db')
DEFAULT_DATA_PATH = os.path.join(project_root, 'account_data_path')
LOCAL_DB = os.environ.get('JAILBIRD_DB_PATH', DEFAULT_DB_PATH)
DATA_PATH = os.environ.get('JAILBIRD_DATA_PATH', DEFAULT_DATA_PATH)

# 确保数据目录存在
os.makedirs(os.path.dirname(LOCAL_DB), exist_ok=True)
os.makedirs(DATA_PATH, exist_ok=True)

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.last_modified = {}

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            current_time = time.time()
            if event.src_path not in self.last_modified or \
               current_time - self.last_modified[event.src_path] > 1:
                self.last_modified[event.src_path] = current_time
                print(f"检测到文件变化: {event.src_path}")
                self.sync_file(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            print(f"检测到文件删除: {event.src_path}")
            self.delete_file(event.src_path)

    def sync_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 计算相对路径，确保正确处理不同操作系统的路径分隔符
            try:
                relative_path = os.path.relpath(file_path, DATA_PATH)
                # 统一使用正斜杠作为路径分隔符
                relative_path = relative_path.replace('\\', '/')
            except ValueError as e:
                # 如果出现路径问题（如不同驱动器），使用文件名作为相对路径
                print(f"[WARNING] 无法计算相对路径，使用文件名: {e}")
                relative_path = os.path.basename(file_path)
                
            key = f"jailbird:account:{relative_path}"
            
            self.redis_client.set(key, json.dumps(data))
            
            sync_message = {
                'key': key,
                'value': data,
                'timestamp': datetime.now().isoformat()
            }
            self.redis_client.publish(SYNC_CHANNEL, json.dumps(sync_message))
            print(f"[OK] 成功同步并发布: {file_path} -> {key}")
            
        except Exception as e:
            print(f"[ERROR] 同步失败 {file_path}: {e}")
            traceback.print_exc()

    def delete_file(self, file_path):
        try:
            # 计算相对路径，确保正确处理不同操作系统的路径分隔符
            try:
                relative_path = os.path.relpath(file_path, DATA_PATH)
                # 统一使用正斜杠作为路径分隔符
                relative_path = relative_path.replace('\\', '/')
            except ValueError as e:
                # 如果出现路径问题（如不同驱动器），使用文件名作为相对路径
                print(f"[WARNING] 无法计算相对路径，使用文件名: {e}")
                relative_path = os.path.basename(file_path)
                
            key = f"jailbird:account:{relative_path}"
            
            delete_message = {
                'key': key,
                'timestamp': datetime.now().isoformat()
            }
            self.redis_client.publish(DELETE_CHANNEL, json.dumps(delete_message))
            print(f"[OK] 已发布删除消息: {file_path} -> {key}")
            
        except Exception as e:
            print(f"[ERROR] 处理删除失败 {file_path}: {e}")
            traceback.print_exc()

def initial_sync(redis_client):
    """初始同步所有文件"""
    print(f"开始初始同步目录: {DATA_PATH}")
    if not os.path.exists(DATA_PATH):
        print(f"[WARNING] 数据目录不存在: {DATA_PATH}")
        os.makedirs(DATA_PATH, exist_ok=True)
        return

    handler = FileChangeHandler(redis_client)
    file_count = 0
    
    for root, dirs, files in os.walk(DATA_PATH):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                try:
                    handler.sync_file(file_path)
                    file_count += 1
                except Exception as e:
                    print(f"[ERROR] 初始同步文件失败 {file_path}: {e}")
                    traceback.print_exc()
    
    print(f"初始同步完成，共同步 {file_count} 个文件")

def handle_sync_message(message, data_path):
    """处理同步消息"""
    try:
        data = json.loads(message['data'])
        key = data.get('key')
        value = data.get('value')
        
        if key and value:
            # 从key中提取相对路径
            relative_path = key.replace('jailbird:account:', '')
            
            # 根据操作系统转换路径分隔符
            if os.name == 'nt':  # Windows系统
                # 确保相对路径使用Windows风格的反斜杠
                relative_path = relative_path.replace('/', '\\')
            else:  # Unix/Linux系统
                # 确保相对路径使用Unix风格的正斜杠
                relative_path = relative_path.replace('\\', '/')
                
            file_path = os.path.join(data_path, relative_path)
            
            # 确保目录存在
            directory = os.path.dirname(file_path)
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(value, f, ensure_ascii=False, indent=4)
            
            print(f"[OK] 已更新文件: {file_path} (from key: {key})")
    except Exception as e:
        print(f"[ERROR] 处理同步消息失败: {e}")
        traceback.print_exc()

def handle_delete_message(message, data_path):
    """处理删除消息"""
    try:
        data = json.loads(message['data'])
        key = data.get('key')
        
        if key:
            # 从key中提取相对路径
            relative_path = key.replace('jailbird:account:', '')
            
            # 根据操作系统转换路径分隔符
            if os.name == 'nt':  # Windows系统
                # 确保相对路径使用Windows风格的反斜杠
                relative_path = relative_path.replace('/', '\\')
            else:  # Unix/Linux系统
                # 确保相对路径使用Unix风格的正斜杠
                relative_path = relative_path.replace('\\', '/')
                
            file_path = os.path.join(data_path, relative_path)
            
            # 删除文件
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[OK] 已删除文件: {file_path} (from key: {key})")
            else:
                print(f"[WARNING] 文件不存在，无法删除: {file_path} (from key: {key})")
    except Exception as e:
        print(f"[ERROR] 处理删除消息失败: {e}")
        traceback.print_exc()

def start_subscriber(redis_client, data_path):
    """启动订阅服务"""
    pubsub = redis_client.pubsub()
    pubsub.subscribe(SYNC_CHANNEL, DELETE_CHANNEL)
    
    print(f"开始监听频道: {SYNC_CHANNEL}, {DELETE_CHANNEL}")
    
    try:
        for message in pubsub.listen():
            if message['type'] == 'message':
                if message['channel'] == SYNC_CHANNEL:
                    handle_sync_message(message, data_path)
                elif message['channel'] == DELETE_CHANNEL:
                    handle_delete_message(message, data_path)
    except Exception as e:
        print(f"[ERROR] 订阅服务出错: {e}")
    finally:
        pubsub.unsubscribe()

def test_redis_connection(redis_client):
    """测试Redis连接"""
    try:
        # 测试基本连接
        redis_client.ping()
        print("[OK] Redis连接测试成功")
        
        # 测试写入权限
        test_key = "test:connection"
        redis_client.set(test_key, "test")
        redis_client.delete(test_key)
        print("[OK] Redis写入权限测试成功")
        
        # 检查现有数据
        orders_count = redis_client.hlen(ORDERS_HASH)
        print(f"[INFO] 当前Redis订单数量: {orders_count}")
        
        return True
    except redis.RedisError as e:
        print(f"[ERROR] Redis连接测试失败: {e}")
        traceback.print_exc()
        return False

def run_local():
    """本地运行模式"""
    # 输出实际使用的路径，便于调试
    print(f"使用数据库路径: {LOCAL_DB}")
    print(f"使用数据目录: {DATA_PATH}")
    
    try:
        # 初始化Redis客户端
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # 测试Redis连接
        if not test_redis_connection(redis_client):
            print("[ERROR] Redis连接失败，程序退出")
            return
        
        # 初始化本地存储
        local_storage = DataStorage(LOCAL_DB)
        
        # 初始化Redis同步管理器
        redis_sync = RedisSyncManager(
            storage=local_storage,
            redis_host=REDIS_HOST,
            redis_port=REDIS_PORT,
            redis_db=REDIS_DB,
            redis_password=REDIS_PASSWORD
        )
        
        # 启动数据库同步
        redis_sync.start_sync(is_cloud=False)
        
        # 设置文件监控
        event_handler = FileChangeHandler(redis_client)
        observer = Observer()
        observer.schedule(event_handler, DATA_PATH, recursive=True)
        observer.start()
        
        try:
            # 执行初始同步
            print("执行初始同步...")
            initial_sync(redis_client)
            print("初始同步完成！")
            
            # 保持运行
            while True:
                # 定期检查Redis连接
                if not test_redis_connection(redis_client):
                    print("[WARNING] Redis连接已断开，尝试重新连接...")
                    time.sleep(5)
                    continue
                time.sleep(30)  # 每30秒检查一次连接
                
        except KeyboardInterrupt:
            print("\n停止监控...")
            observer.stop()
            redis_sync.stop_sync()
        observer.join()
    except Exception as e:
        print(f"[ERROR] 运行出错: {e}")
        traceback.print_exc()

def run_cloud():
    """云端运行模式"""
    try:
        # 输出实际使用的路径，便于调试
        # cloud_db_path = os.path.join(current_dir, "cloud_trading_data.db")
        cloud_db_path = os.getenv('TRADING_DATA_PATH')
        print(f"使用云端数据库路径: {cloud_db_path}")
        print(f"使用数据目录: {DATA_PATH}")
        
        # 初始化Redis客户端
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        
        # 测试Redis连接
        if not test_redis_connection(redis_client):
            print("[ERROR] Redis连接失败，程序退出")
            return
        
        # 初始化云端存储
        cloud_storage = DataStorage(cloud_db_path)
        
        # 初始化Redis同步管理器
        redis_sync = RedisSyncManager(
            storage=cloud_storage,
            redis_host=REDIS_HOST,
            redis_port=REDIS_PORT,
            redis_db=REDIS_DB,
            redis_password=REDIS_PASSWORD
        )
        
        # 启动数据库同步
        redis_sync.start_sync(is_cloud=True)
        
        # 启动文件订阅服务
        subscriber_thread = threading.Thread(
            target=start_subscriber,
            args=(redis_client, DATA_PATH),
            daemon=True
        )
        subscriber_thread.start()
        
        try:
            while True:
                # 定期检查Redis连接
                if not test_redis_connection(redis_client):
                    print("[WARNING] Redis连接已断开，尝试重新连接...")
                    time.sleep(5)
                    continue
                time.sleep(30)  # 每30秒检查一次连接
                
        except KeyboardInterrupt:
            print("\n停止同步...")
            redis_sync.stop_sync()
    except Exception as e:
        print(f"[ERROR] 运行出错: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cloud":
        print("运行云端模式...")
        run_cloud()
    else:
        print("运行本地模式...")
        run_local() 