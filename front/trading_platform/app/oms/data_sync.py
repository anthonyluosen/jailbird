import os
import time
import json
import shutil
import sqlite3
import pandas as pd
import threading
from pathlib import Path
from datetime import datetime
from flask_socketio import SocketIO
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class DataSynchronizer:
    """处理多种格式数据的同步器"""
    
    def __init__(self, socketio, config=None):
        self.socketio = socketio
        self.config = config or {}
        self.default_interval = self.config.get('interval', 5)  # 默认5秒
        self.sync_threads = {}
        self.file_watchers = {}
        self.running = False
    
    def start(self):
        """启动同步服务"""
        self.running = True
        print("数据同步服务已启动")
    
    def stop(self):
        """停止同步服务"""
        self.running = False
        for thread in self.sync_threads.values():
            thread.join(timeout=1.0)
        for observer in self.file_watchers.values():
            observer.stop()
            observer.join()
        print("数据同步服务已停止")
    
    def sync_database(self, local_path, data_type, interval=None):
        """同步SQLite数据库"""
        interval = interval or self.default_interval
        
        def _sync_db():
            last_mtime = 0
            while self.running:
                try:
                    # 检查文件是否更新
                    current_mtime = os.path.getmtime(local_path)
                    if current_mtime > last_mtime:
                        print(f"检测到数据库变化: {local_path}")
                        # 从数据库读取新数据
                        conn = sqlite3.connect(local_path)
                        cursor = conn.cursor()
                        cursor.execute(f"SELECT * FROM {data_type} ORDER BY id DESC LIMIT 100")
                        columns = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()
                        data = [dict(zip(columns, row)) for row in rows]
                        conn.close()
                        
                        # 通过WebSocket推送更新
                        self.socketio.emit(f'update_{data_type}', data, namespace='/oms')
                        last_mtime = current_mtime
                except Exception as e:
                    print(f"同步数据库失败: {e}")
                time.sleep(interval)
        
        thread = threading.Thread(target=_sync_db, daemon=True)
        thread.start()
        self.sync_threads[f"db_{local_path}"] = thread
        return thread
    
    def sync_csv(self, local_path, data_type, interval=None):
        """同步CSV文件"""
        interval = interval or self.default_interval
        
        def _sync_csv():
            last_mtime = 0
            while self.running:
                try:
                    # 检查文件是否更新
                    current_mtime = os.path.getmtime(local_path)
                    if current_mtime > last_mtime:
                        print(f"检测到CSV文件变化: {local_path}")
                        # 从CSV读取数据
                        df = pd.read_csv(local_path)
                        data = df.to_dict(orient='records')
                        
                        # 通过WebSocket推送更新
                        self.socketio.emit(f'update_{data_type}', data, namespace='/oms')
                        last_mtime = current_mtime
                except Exception as e:
                    print(f"同步CSV文件失败: {e}")
                time.sleep(interval)
        
        thread = threading.Thread(target=_sync_csv, daemon=True)
        thread.start()
        self.sync_threads[f"csv_{local_path}"] = thread
        return thread
    
    def sync_json_folder(self, folder_path, data_type):
        """同步JSON文件夹（使用文件系统监控）"""
        
        class JsonFolderHandler(FileSystemEventHandler):
            def __init__(self, parent):
                self.parent = parent
            
            def on_modified(self, event):
                if event.is_directory:
                    return
                if event.src_path.endswith('.json'):
                    print(f"检测到JSON文件变化: {event.src_path}")
                    try:
                        with open(event.src_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        # 通过WebSocket推送更新
                        self.parent.socketio.emit(
                            f'update_{data_type}', 
                            {'file': os.path.basename(event.src_path), 'data': data}, 
                            namespace='/oms'
                        )
                    except Exception as e:
                        print(f"处理JSON文件变化失败: {e}")
        
        # 创建观察者
        event_handler = JsonFolderHandler(self)
        observer = Observer()
        observer.schedule(event_handler, folder_path, recursive=True)
        observer.start()
        self.file_watchers[folder_path] = observer
        return observer

# 在应用启动时初始化
def init_data_sync(app, socketio):
    """初始化数据同步服务"""
    data_sync = DataSynchronizer(socketio)
    
    # 添加到应用上下文
    app.data_sync = data_sync
    
    # 启动同步服务
    data_sync.start()
    
    # 配置需要同步的数据
    if os.getenv('TRADING_DATA_PATH'):
        data_sync.sync_database(
            os.getenv('TRADING_DATA_PATH'), 
            'orders'
        )
    
    # 如果有回测数据
    backtest_dir = os.getenv('BACKTEST_RESULTS_PATH')
    if backtest_dir and os.path.exists(backtest_dir):
        data_sync.sync_json_folder(backtest_dir, 'backtest')
    
    # 如果有持仓数据CSV
    positions_csv = os.getenv('POSITIONS_CSV_PATH')
    if positions_csv and os.path.exists(positions_csv):
        data_sync.sync_csv(positions_csv, 'positions')
    
    return data_sync 