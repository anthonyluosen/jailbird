import sys
sys.path.append(r'F:\workspace\jailbird\front\trading_platform')
import json
import redis
import threading
import time
import traceback
from typing import Optional
from datetime import datetime
from trading_platform.app.oms.constant import Order
from trading_platform.app.oms.storage import DataStorage

class RedisSyncManager:
    """Redis同步管理器，负责本地数据库和Redis之间的数据同步"""
    def __init__(self, 
                 storage: DataStorage,
                 redis_host: str = 'localhost', 
                 redis_port: int = 6379, 
                 redis_db: int = 0,
                 sync_interval: int = 5):
        """
        初始化Redis同步管理器
        
        Args:
            storage: DataStorage实例
            redis_host: Redis服务器地址
            redis_port: Redis服务器端口
            redis_db: Redis数据库编号
            sync_interval: 同步间隔（秒）
        """
        self.storage = storage
        self.redis_client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            db=redis_db,
            decode_responses=True  # 自动解码响应
        )
        self.sync_thread = None
        self.running = False
        self.sync_interval = sync_interval
        self.is_cloud = False  # 标记是否为云端实例
        
    def start_sync(self, is_cloud: bool = False):
        """
        启动同步线程
        
        Args:
            is_cloud: 是否为云端实例
        """
        self.is_cloud = is_cloud
        if not self.sync_thread or not self.sync_thread.is_alive():
            self.running = True
            self.sync_thread = threading.Thread(target=self._sync_loop)
            self.sync_thread.daemon = True
            self.sync_thread.start()
            
    def stop_sync(self):
        """停止同步线程"""
        self.running = False
        if self.sync_thread:
            self.sync_thread.join()
            
    def _sync_loop(self):
        """同步循环"""
        while self.running:
            try:
                self._sync_orders()
                time.sleep(self.sync_interval)
            except Exception as e:
                print(f"同步过程中出错: {e}")
                traceback.print_exc()
                
    def _sync_orders(self):
        """同步订单数据"""
        if self.is_cloud:
            # 云端模式：从本地数据库同步到Redis
            orders = self.storage.get_active_orders()
            for order in orders:
                self.publish_order(order)
        else:
            # 本地模式：从Redis同步到本地数据库
            redis_orders = self.redis_client.hgetall('orders')
            for order_id, order_data in redis_orders.items():
                try:
                    order_dict = json.loads(order_data)
                    order = Order(**order_dict)
                    # 更新本地数据库
                    self.storage.save_order(order)
                except Exception as e:
                    print(f"处理Redis订单数据时出错: {e}")
                
    def publish_order(self, order: Order):
        """发布订单到Redis"""
        try:
            order_dict = self.storage._serialize_order(order)
            self.redis_client.hset('orders', order.order_id, json.dumps(order_dict))
        except Exception as e:
            print(f"发布订单到Redis时出错: {e}")
            
    def delete_order(self, order_id: str):
        """从Redis删除订单"""
        try:
            self.redis_client.hdel('orders', order_id)
        except Exception as e:
            print(f"从Redis删除订单时出错: {e}")
            
    def get_redis_orders(self) -> dict:
        """获取Redis中的所有订单"""
        try:
            return self.redis_client.hgetall('orders')
        except Exception as e:
            print(f"获取Redis订单时出错: {e}")
            return {}
            
    def clear_redis_orders(self):
        """清空Redis中的所有订单"""
        try:
            self.redis_client.delete('orders')
        except Exception as e:
            print(f"清空Redis订单时出错: {e}") 