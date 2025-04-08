import sys
import json
import redis
import threading
import time
import traceback
from typing import Optional, Dict
from datetime import datetime
from app.oms.constant import Order
from app.oms.storage import DataStorage

class RedisSyncManager:
    """Redis同步管理器，负责本地数据库和Redis之间的数据同步"""
    def __init__(self, 
                 storage: DataStorage,
                 redis_host: str = 'localhost', 
                 redis_port: int = 6379, 
                 redis_db: int = 0,
                 sync_interval: int = 5,
                 redis_password: str = '123'):
        """
        初始化Redis同步管理器
        
        Args:
            storage: DataStorage实例
            redis_host: Redis服务器地址
            redis_port: Redis服务器端口
            redis_db: Redis数据库编号
            sync_interval: 同步间隔（秒）
            redis_password: Redis密码
        """
        self.storage = storage
        self.redis_client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            db=redis_db,
            password=redis_password,  # 添加密码认证
            decode_responses=True  # 自动解码响应
        )
        self.sync_thread = None
        self.monitor_thread = None
        self.running = False
        self.sync_interval = sync_interval
        self.is_cloud = False  # 标记是否为云端实例
        self.last_orders: Dict[str, Order] = {}  # 用于跟踪上次同步的订单状态
        
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
            
        if not self.monitor_thread or not self.monitor_thread.is_alive():
            self.monitor_thread = threading.Thread(target=self._monitor_local_changes)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
    def stop_sync(self):
        """停止同步线程"""
        self.running = False
        if self.sync_thread:
            self.sync_thread.join()
        if self.monitor_thread:
            self.monitor_thread.join()
            
    def _monitor_local_changes(self):
        """监控本地数据库变化"""
        while self.running:
            try:
                current_orders = self.storage.get_active_orders()
                current_orders_dict = {order.order_id: order for order in current_orders}
                
                # 检查新增或更新的订单
                for order_id, order in current_orders_dict.items():
                    if order_id not in self.last_orders or self.last_orders[order_id] != order:
                        # 订单是新增的或已更新
                        self.publish_order(order)
                
                # 检查删除的订单
                for order_id in self.last_orders:
                    if order_id not in current_orders_dict:
                        # 订单已被删除
                        self.delete_order(order_id)
                
                # 更新最后已知的订单状态
                self.last_orders = current_orders_dict
                
                time.sleep(self.sync_interval)
            except Exception as e:
                print(f"监控本地数据库变化时出错: {e}")
                traceback.print_exc()
                time.sleep(self.sync_interval)
                
    def _sync_loop(self):
        """同步循环"""
        while self.running:
            try:
                if self.is_cloud:
                    # 云端模式：从Redis同步到本地数据库
                    redis_orders = self.redis_client.hgetall('orders')
                    for order_id, order_data in redis_orders.items():
                        try:
                            order_dict = json.loads(order_data)
                            order = Order(**order_dict)
                            
                            # 检查订单是否已存在且未更新
                            existing_order = self.storage.get_order(order_id)
                            if existing_order:
                                # 如果订单已存在，检查是否需要更新
                                if existing_order.status == order.status and \
                                   existing_order.filled_volume == order.filled_volume and \
                                   existing_order.traded_price == order.traded_price:
                                    # 如果订单状态和成交信息没有变化，跳过更新
                                    continue
                            
                            # 保存或更新订单
                            self.storage.save_order(order)
                            print(f"[OK] 云端已同步订单: {order_id}")
                            
                        except Exception as e:
                            print(f"[ERROR] 处理Redis订单数据时出错: {e}")
                            traceback.print_exc()
                else:
                    # 本地模式：从Redis同步到本地数据库
                    redis_orders = self.redis_client.hgetall('orders')
                    for order_id, order_data in redis_orders.items():
                        try:
                            order_dict = json.loads(order_data)
                            order = Order(**order_dict)
                            self.storage.save_order(order)
                        except Exception as e:
                            print(f"[ERROR] 处理Redis订单数据时出错: {e}")
                time.sleep(self.sync_interval)
            except Exception as e:
                print(f"[ERROR] 同步过程中出错: {e}")
                traceback.print_exc()
                time.sleep(self.sync_interval)
                
    def publish_order(self, order: Order):
        """发布订单到Redis"""
        try:
            # 确保order_id是字符串类型
            order_id = str(order.order_id)
            # 序列化订单数据
            order_dict = self.storage._serialize_order(order)
            # 将订单数据转换为JSON字符串
            order_json = json.dumps(order_dict)
            # 使用正确的hset参数格式
            self.redis_client.hset('orders', order_id, order_json)
        except Exception as e:
            print(f"发布订单到Redis时出错: {e}")
            traceback.print_exc()
            
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