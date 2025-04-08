import redis
import json
import os
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

# Redis连接配置
REDIS_HOST = '1.95.154.244'
REDIS_PORT = 6379
REDIS_PASSWORD = '123'
CHANNEL_NAME = 'jailbird:sync'
DELETE_CHANNEL_NAME = 'jailbird:delete'

# 本地数据路径
DATA_PATH = r'F:/workspace/code/account_data_path'

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.last_modified = {}  # 记录文件最后修改时间

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            current_time = time.time()
            # 检查文件是否真的发生了变化（避免重复触发）
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
        """同步单个文件到Redis"""
        try:
            # 读取JSON数据
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 构造Redis键名
            relative_path = os.path.relpath(file_path, DATA_PATH)
            key = f"jailbird:account:{relative_path}"
            
            # 将数据存储到本地Redis
            self.redis_client.set(key, json.dumps(data))
            
            # 发布同步消息到频道
            sync_message = {
                'key': key,
                'value': data,
                'timestamp': datetime.now().isoformat()
            }
            self.redis_client.publish(CHANNEL_NAME, json.dumps(sync_message))
            print(f"✅ 成功同步并发布: {relative_path}")
            
        except Exception as e:
            print(f"❌ 同步失败 {file_path}: {e}")

    def delete_file(self, file_path):
        """处理文件删除"""
        try:
            # 构造Redis键名
            relative_path = os.path.relpath(file_path, DATA_PATH)
            key = f"jailbird:account:{relative_path}"
            
            # 发布删除消息到频道
            delete_message = {
                'key': key,
                'timestamp': datetime.now().isoformat()
            }
            self.redis_client.publish(DELETE_CHANNEL_NAME, json.dumps(delete_message))
            print(f"✅ 已发布删除消息: {relative_path}")
            
        except Exception as e:
            print(f"❌ 处理删除失败 {file_path}: {e}")

def connect_redis():
    """连接到Redis服务器"""
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        r.ping()
        print("✅ Redis连接成功！")
        return r
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
        return None

def initial_sync(redis_client):
    """初始同步所有文件"""
    for root, dirs, files in os.walk(DATA_PATH):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                handler = FileChangeHandler(redis_client)
                handler.sync_file(file_path)

def scan_and_update_redis(redis_client):
    """扫描Redis并更新数据"""
    try:
        print("开始扫描Redis数据...")
        missing_files = []  # 存储不存在的文件路径
        
        # 获取所有jailbird:account:开头的键
        keys = redis_client.keys("jailbird:account:*")
        for key in keys:
            if not key.endswith(":metadata") and not key.endswith(":version"):
                try:
                    # 获取数据
                    data = redis_client.get(key)
                    if data:
                        # 解析数据
                        json_data = json.loads(data)
                        
                        # 构造文件路径
                        relative_path = key.replace("jailbird:account:", "")
                        file_path = os.path.join(DATA_PATH, relative_path)
                        
                        # 检查文件是否存在
                        if not os.path.exists(file_path):
                            missing_files.append(key)
                            print(f"⚠️ 文件不存在: {relative_path}")
                            # 发布删除消息到频道
                            delete_message = {
                                'key': key,
                                'timestamp': datetime.now().isoformat()
                            }
                            redis_client.publish(DELETE_CHANNEL_NAME, json.dumps(delete_message))
                            print(f"✅ 已发布删除消息: {relative_path}")
                            continue
                        
                        # 确保目录存在
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        
                        # 写入文件
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(json_data, f, ensure_ascii=False, indent=4)
                        
                        print(f"✅ 已更新文件: {relative_path}")
                except Exception as e:
                    print(f"❌ 处理键 {key} 时出错: {e}")
        
        # 输出不存在的文件列表
        if missing_files:
            print("\n以下文件在本地不存在，已发送删除信号：")
            for key in missing_files:
                relative_path = key.replace("jailbird:account:", "")
                print(f"- {relative_path}")
        else:
            print("\n所有文件都已存在")
        
        print("Redis数据扫描和更新完成！")
    except Exception as e:
        print(f"❌ 扫描Redis时出错: {e}")

def main():
    print("开始数据同步服务...")
    redis_client = connect_redis()
    if not redis_client:
        return

    # 扫描并更新Redis数据
    scan_and_update_redis(redis_client)

    # 初始同步所有文件
    print("执行初始同步...")
    initial_sync(redis_client)
    print("初始同步完成！")

    # 设置文件监控
    event_handler = FileChangeHandler(redis_client)
    observer = Observer()
    observer.schedule(event_handler, DATA_PATH, recursive=True)
    observer.start()
    print(f"开始监控目录: {DATA_PATH}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止监控...")
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main() 