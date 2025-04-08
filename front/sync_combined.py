import sys
import sys
sys.path.append(r'F:\workspace\jailbird\front\trading_platform')
import redis
import json
import os
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

# 本地配置
LOCAL_DB = r'F:/workspace/code/trading_data.db'
DATA_PATH = r'F:/workspace/code/account_data_path'

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
            
            relative_path = os.path.relpath(file_path, DATA_PATH)
            key = f"jailbird:account:{relative_path}"
            
            self.redis_client.set(key, json.dumps(data))
            
            sync_message = {
                'key': key,
                'value': data,
                'timestamp': datetime.now().isoformat()
            }
            self.redis_client.publish(SYNC_CHANNEL, json.dumps(sync_message))
            print(f"[OK] 成功同步并发布: {relative_path}")
            
        except Exception as e:
            print(f"[ERROR] 同步失败 {file_path}: {e}")

    def delete_file(self, file_path):
        try:
            relative_path = os.path.relpath(file_path, DATA_PATH)
            key = f"jailbird:account:{relative_path}"
            
            delete_message = {
                'key': key,
                'timestamp': datetime.now().isoformat()
            }
            self.redis_client.publish(DELETE_CHANNEL, json.dumps(delete_message))
            print(f"[OK] 已发布删除消息: {relative_path}")
            
        except Exception as e:
            print(f"[ERROR] 处理删除失败 {file_path}: {e}")

def initial_sync(redis_client):
    """初始同步所有文件"""
    for root, dirs, files in os.walk(DATA_PATH):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                handler = FileChangeHandler(redis_client)
                handler.sync_file(file_path)

def handle_sync_message(message, data_path):
    """处理同步消息"""
    try:
        data = json.loads(message['data'])
        key = data.get('key')
        value = data.get('value')
        
        if key and value:
            # 从key中提取相对路径
            relative_path = key.replace('jailbird:account:', '')
            file_path = os.path.join(data_path, relative_path)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(value, f, ensure_ascii=False, indent=4)
            
            print(f"[OK] 已更新文件: {relative_path}")
    except Exception as e:
        print(f"[ERROR] 处理同步消息失败: {e}")

def handle_delete_message(message, data_path):
    """处理删除消息"""
    try:
        data = json.loads(message['data'])
        key = data.get('key')
        
        if key:
            # 从key中提取相对路径
            relative_path = key.replace('jailbird:account:', '')
            file_path = os.path.join(data_path, relative_path)
            
            # 删除文件
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"[OK] 已删除文件: {relative_path}")
    except Exception as e:
        print(f"[ERROR] 处理删除消息失败: {e}")

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

def run_local():
    """本地运行模式"""
    # 初始化本地存储
    local_storage = DataStorage(LOCAL_DB)
    
    # 初始化Redis客户端
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    
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
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n停止监控...")
        observer.stop()
        redis_sync.stop_sync()
    observer.join()

def run_cloud():
    """云端运行模式"""
    # 初始化云端存储
    cloud_storage = DataStorage("cloud_trading_data.db")
    
    # 初始化Redis客户端
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    
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
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n停止同步...")
        redis_sync.stop_sync()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cloud":
        print("运行云端模式...")
        run_cloud()
    else:
        print("运行本地模式...")
        run_local() 