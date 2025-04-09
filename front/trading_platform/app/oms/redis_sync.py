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
        
        # Redis键名
        self.ORDERS_HASH = 'jailbird:account:orders'
        
        # 测试Redis连接
        self._test_connection()
        
    def _test_connection(self):
        """测试Redis连接"""
        try:
            self.redis_client.ping()
            print("[OK] Redis连接测试成功")
            return True
        except redis.RedisError as e:
            print(f"[ERROR] Redis连接测试失败: {e}")
            traceback.print_exc()
            return False
            
    def start_sync(self, is_cloud: bool = False):
        """
        启动同步线程
        
        Args:
            is_cloud: 是否为云端实例
        """
        # 在启动同步之前先测试Redis连接
        print("正在测试Redis连接...")
        self._test_connection()
        
        self.is_cloud = is_cloud
        if not self.sync_thread or not self.sync_thread.is_alive():
            self.running = True
            self.sync_thread = threading.Thread(target=self._sync_loop)
            self.sync_thread.daemon = True
            self.sync_thread.start()
            print(f"已启动{'云端' if is_cloud else '本地'}同步线程")
            
        if not self.monitor_thread or not self.monitor_thread.is_alive():
            self.monitor_thread = threading.Thread(target=self._monitor_local_changes)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            print("已启动本地监控线程")
            
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
                # 获取所有活跃订单
                current_orders = self.storage.get_active_orders()
                print(f"[DEBUG] 获取到本地活跃订单数量: {len(current_orders)}")
                
                current_orders_dict = {str(order.order_id): order for order in current_orders if order.order_id}
                print(f"[DEBUG] 有效订单数量: {len(current_orders_dict)}")
                
                # 检查新增或更新的订单
                for order_id, order in current_orders_dict.items():
                    try:
                        # 跳过空order_id
                        if not order_id or order_id == "None" or order_id == "null":
                            print(f"[DEBUG] 跳过空order_id的订单")
                            continue
                            
                        # 检查订单是否需要更新
                        if order_id in self.last_orders:
                            last_order = self.last_orders[order_id]
                            last_status = getattr(last_order.status, 'value', None)
                            current_status = getattr(order.status, 'value', None)
                            print(f"[DEBUG] 订单 {order_id} 状态对比 - 旧状态: {last_status}, 新状态: {current_status}")
                            
                            # 只有当关键信息发生变化时才更新
                            if (last_status == current_status and
                                last_order.filled_volume == order.filled_volume and
                                last_order.traded_price == order.traded_price):
                                print(f"[DEBUG] 订单 {order_id} 无变化，跳过更新")
                                continue
                        else:
                            print(f"[DEBUG] 发现新订单: {order_id}")
                        
                        # 发布订单到Redis
                        self.publish_order(order)
                        print(f"[OK] 本地推送订单到Redis: {order_id}, 状态: {getattr(order.status, 'value', None)}")
                    except Exception as e:
                        print(f"[ERROR] 处理订单时出错 {order_id}: {e}")
                        traceback.print_exc()
                
                # 检查删除的订单
                deleted_orders = set(self.last_orders.keys()) - set(current_orders_dict.keys())
                if deleted_orders:
                    print(f"[DEBUG] 发现已删除的订单: {deleted_orders}")
                    
                for order_id in deleted_orders:
                    try:
                        # 订单已被删除
                        self.delete_order(order_id)
                        print(f"[OK] 从Redis删除订单: {order_id}")
                    except Exception as e:
                        print(f"[ERROR] 删除订单时出错 {order_id}: {e}")
                        traceback.print_exc()
                
                # 更新最后已知的订单状态
                self.last_orders = current_orders_dict
                
                time.sleep(self.sync_interval)
            except Exception as e:
                print(f"[ERROR] 监控本地数据库变化时出错: {e}")
                traceback.print_exc()
                time.sleep(self.sync_interval)
                
    def _sync_loop(self):
        """同步循环"""
        while self.running:
            try:
                # 首先测试连接
                if not self._test_connection():
                    print("[WARNING] Redis连接已断开，等待重试...")
                    time.sleep(5)
                    continue
                    
                if self.is_cloud:
                    # 云端模式：从Redis同步到本地数据库
                    redis_orders = self.redis_client.hgetall(self.ORDERS_HASH)
                    print(f"[DEBUG] 从Redis获取到 {len(redis_orders)} 个订单")
                    
                    for order_id, order_data in redis_orders.items():
                        try:
                            order_dict = json.loads(order_data)
                            order = Order(**order_dict)
                            
                            # 检查order_id是否为空
                            if not order_id or order_id == "None" or order_id == "null":
                                print(f"[WARNING] 跳过空order_id的订单")
                                continue
                            
                            # 检查订单是否已存在且未更新
                            existing_order = self.storage.get_order(order_id)
                            if existing_order:
                                # 使用创建时间比较
                                if hasattr(existing_order, 'create_time') and hasattr(order, 'create_time'):
                                    # 检查订单状态等其他关键信息
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
                    redis_orders = self.redis_client.hgetall(self.ORDERS_HASH)
                    print(f"[DEBUG] 从Redis获取到 {len(redis_orders)} 个订单")
                    
                    for order_id, order_data in redis_orders.items():
                        try:
                            order_dict = json.loads(order_data)
                            order = Order(**order_dict)
                            
                            # 检查order_id是否为空
                            if not order_id or order_id == "None" or order_id == "null":
                                print(f"[WARNING] 跳过空order_id的订单")
                                continue
                            
                            # 检查订单是否已存在且未更新
                            existing_order = self.storage.get_order(order_id)
                            if existing_order:
                                # 使用创建时间比较
                                if hasattr(existing_order, 'create_time') and hasattr(order, 'create_time'):
                                    # 检查订单状态等其他关键信息
                                    if existing_order.status == order.status and \
                                       existing_order.filled_volume == order.filled_volume and \
                                       existing_order.traded_price == order.traded_price:
                                        # 如果订单状态和成交信息没有变化，跳过更新
                                        continue
                            
                            # 保存或更新订单
                            self.storage.save_order(order)
                            print(f"[OK] 本地已同步订单: {order_id}")
                            
                        except Exception as e:
                            print(f"[ERROR] 处理Redis订单数据时出错: {e}")
                            traceback.print_exc()
                time.sleep(self.sync_interval)
            except Exception as e:
                print(f"[ERROR] 同步过程中出错: {e}")
                traceback.print_exc()
                time.sleep(self.sync_interval)
                
    def publish_order(self, order: Order):
        """发布订单到Redis"""
        try:
            # 确保order_id是字符串类型
            order_id = str(order.order_id) if order.order_id is not None else None
            
            # 跳过空order_id
            if not order_id or order_id == "None" or order_id == "null":
                print(f"[WARNING] 跳过发布空order_id的订单")
                return
                
            # 序列化订单数据
            try:
                print(f"[DEBUG] 开始序列化订单 {order_id}")
                order_dict = self.storage._serialize_order(order)
                # 确保status是字符串值
                if 'status' in order_dict and hasattr(order_dict['status'], 'value'):
                    order_dict['status'] = order_dict['status'].value
                print(f"[DEBUG] 订单序列化结果: {order_dict}")
            except Exception as e:
                print(f"[ERROR] 序列化订单数据时出错: {e}")
                traceback.print_exc()
                return
                
            # 将订单数据转换为JSON字符串
            try:
                order_json = json.dumps(order_dict)
                print(f"[DEBUG] 订单JSON数据: {order_json[:200]}...")  # 只打印前200个字符
            except Exception as e:
                print(f"[ERROR] 转换订单数据为JSON时出错: {e}")
                traceback.print_exc()
                return
                
            # 发布到Redis
            try:
                # 检查Redis连接
                if not self._test_connection():
                    print("[ERROR] Redis连接已断开，无法发布订单")
                    return
                    
                # 检查订单是否已存在
                existing_data = self.redis_client.hget(self.ORDERS_HASH, order_id)
                if existing_data:
                    print(f"[DEBUG] 订单 {order_id} 已存在于Redis中")
                    
                # 写入数据
                result = self.redis_client.hset(self.ORDERS_HASH, order_id, order_json)
                print(f"[DEBUG] Redis hset结果: {result} (1=新增, 0=更新)")
                
                # 验证数据是否成功写入
                saved_data = self.redis_client.hget(self.ORDERS_HASH, order_id)
                if saved_data:
                    if saved_data == order_json:
                        print(f"[OK] 订单已成功写入Redis: {order_id}")
                        # 显示当前Redis中的所有订单数量
                        total_orders = self.redis_client.hlen(self.ORDERS_HASH)
                        print(f"[INFO] Redis中当前共有 {total_orders} 个订单")
                    else:
                        print(f"[WARNING] 订单数据不匹配: {order_id}")
                        print(f"[DEBUG] 期望值: {order_json[:100]}...")
                        print(f"[DEBUG] 实际值: {saved_data[:100]}...")
                else:
                    print(f"[ERROR] 订单写入失败: {order_id}")
                    
                # 列出所有订单的key
                all_keys = self.redis_client.hkeys(self.ORDERS_HASH)
                print(f"[DEBUG] Redis中的所有订单ID: {all_keys}")
                
            except redis.RedisError as e:
                print(f"[ERROR] Redis操作失败: {e}")
                traceback.print_exc()
        except Exception as e:
            print(f"[ERROR] 发布订单到Redis时出错: {e}")
            traceback.print_exc()
            
    def delete_order(self, order_id: str):
        """从Redis删除订单"""
        try:
            # 检查order_id是否为空
            if not order_id or order_id == "None" or order_id == "null":
                print(f"[WARNING] 跳过删除空order_id的订单")
                return
                
            self.redis_client.hdel(self.ORDERS_HASH, order_id)
            print(f"[OK] 已从Redis删除订单: {order_id}")
        except Exception as e:
            print(f"[ERROR] 从Redis删除订单时出错: {e}")
            traceback.print_exc()
            
    def get_redis_orders(self) -> dict:
        """获取Redis中的所有订单"""
        try:
            orders = self.redis_client.hgetall(self.ORDERS_HASH)
            print(f"[DEBUG] 当前Redis中的订单数量: {len(orders)}")
            return orders
        except Exception as e:
            print(f"[ERROR] 获取Redis订单时出错: {e}")
            traceback.print_exc()
            return {}
            
    def clear_redis_orders(self):
        """清空Redis中的所有订单"""
        try:
            self.redis_client.delete('orders')
        except Exception as e:
            print(f"清空Redis订单时出错: {e}") 