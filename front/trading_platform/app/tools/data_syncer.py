import os
import time
import json
import requests
import sqlite3
import hashlib
import logging
import argparse
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 配置日志
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DataSyncer')

class DataSyncer:
    """独立的数据同步工具"""
    
    def __init__(self, server_url, api_key=None):
        self.server_url = server_url
        self.api_key = api_key
        self.last_sync = {}
        self.running = True
        self.observers = []
    
    def start(self):
        logger.info("数据同步服务已启动")
        
    def stop(self):
        self.running = False
        for observer in self.observers:
            observer.stop()
            observer.join()
        logger.info("数据同步服务已停止")
    
    def sync_database(self, db_path, table_name, interval=5):
        """同步数据库表到服务器"""
        
        def _compute_hash(data):
            """计算数据哈希值，用于检测变化"""
            return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
        
        def _sync_task():
            last_hash = ""
            
            while self.running:
                try:
                    # 检查数据库文件是否存在
                    if not os.path.exists(db_path):
                        logger.warning(f"数据库文件不存在: {db_path}")
                        time.sleep(interval)
                        continue
                    
                    # 从数据库读取数据
                    conn = sqlite3.connect(db_path)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    try:
                        cursor.execute(f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT 100")
                        rows = [dict(row) for row in cursor.fetchall()]
                    except sqlite3.OperationalError as e:
                        logger.error(f"查询数据库失败: {e}")
                        time.sleep(interval)
                        continue
                    finally:
                        conn.close()
                    
                    # 检查数据是否有变化
                    current_hash = _compute_hash(rows)
                    if current_hash != last_hash:
                        logger.info(f"检测到数据变化，正在同步 {table_name}...")
                        
                        # 准备上传数据
                        payload = {
                            "table": table_name,
                            "data": rows,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        # 发送到服务器
                        headers = {"Content-Type": "application/json"}
                        if self.api_key:
                            headers["Authorization"] = f"Bearer {self.api_key}"
                            
                        response = requests.post(
                            f"{self.server_url}/api/sync/{table_name}",
                            json=payload,
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            logger.info(f"{table_name} 同步成功")
                            last_hash = current_hash
                        else:
                            logger.error(f"同步失败: {response.status_code} - {response.text}")
                            
                except Exception as e:
                    logger.error(f"同步过程中出错: {e}", exc_info=True)
                
                time.sleep(interval)
        
        import threading
        sync_thread = threading.Thread(target=_sync_task, daemon=True)
        sync_thread.start()
        return sync_thread
    
    def watch_directory(self, dir_path, pattern="*.json", recursive=True):
        """监视目录变化并同步文件"""
        
        class FileChangeHandler(FileSystemEventHandler):
            def __init__(self, syncer):
                self.syncer = syncer
            
            def on_modified(self, event):
                if event.is_directory:
                    return
                    
                filepath = event.src_path
                if filepath.endswith(pattern.replace("*", "")):
                    self._process_file(filepath)
            
            def on_created(self, event):
                if event.is_directory:
                    return
                    
                filepath = event.src_path
                if filepath.endswith(pattern.replace("*", "")):
                    self._process_file(filepath)
            
            def _process_file(self, filepath):
                try:
                    logger.info(f"处理文件变化: {filepath}")
                    
                    # 读取文件内容
                    with open(filepath, 'rb') as f:
                        file_content = f.read()
                        
                    # 获取相对路径作为标识
                    relative_path = os.path.relpath(filepath, dir_path)
                    
                    # 准备上传
                    files = {'file': (os.path.basename(filepath), file_content)}
                    data = {'path': relative_path}
                    
                    # 发送到服务器
                    headers = {}
                    if self.syncer.api_key:
                        headers["Authorization"] = f"Bearer {self.syncer.api_key}"
                        
                    response = requests.post(
                        f"{self.syncer.server_url}/api/sync/file",
                        files=files,
                        data=data,
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"文件 {relative_path} 同步成功")
                    else:
                        logger.error(f"文件同步失败: {response.status_code} - {response.text}")
                        
                except Exception as e:
                    logger.error(f"处理文件变化时出错: {e}", exc_info=True)
        
        # 创建观察者
        event_handler = FileChangeHandler(self)
        observer = Observer()
        observer.schedule(event_handler, dir_path, recursive=recursive)
        observer.start()
        self.observers.append(observer)
        logger.info(f"开始监视目录: {dir_path}")
        return observer

# 命令行接口
def main():
    parser = argparse.ArgumentParser(description='数据同步工具')
    parser.add_argument('--server', required=True, help='服务器URL')
    parser.add_argument('--api-key', help='API密钥')
    parser.add_argument('--db', help='数据库文件路径')
    parser.add_argument('--table', help='要同步的表名')
    parser.add_argument('--dir', help='要监视的目录路径')
    parser.add_argument('--interval', type=int, default=5, help='同步间隔(秒)')
    
    args = parser.parse_args()
    
    syncer = DataSyncer(args.server, args.api_key)
    syncer.start()
    
    try:
        if args.db and args.table:
            syncer.sync_database(args.db, args.table, args.interval)
            
        if args.dir:
            syncer.watch_directory(args.dir)
            
        # 保持程序运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在停止...")
    finally:
        syncer.stop()

if __name__ == "__main__":
    main() 