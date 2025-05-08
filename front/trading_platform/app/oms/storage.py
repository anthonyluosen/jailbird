from typing import Dict, List, Optional
import json
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from dataclasses import asdict
from app.oms.constant import Order, Event, EventType, OrderStatus, OrderSide, OrderType
import traceback
import os

class EnumEncoder(json.JSONEncoder):
    """处理枚举类型的JSON编码器"""
    def default(self, obj):
        # 处理所有枚举类型
        if hasattr(obj, "value") and not isinstance(obj, type):
            return obj.value
        # 使用类型名称字符串来检查，避免变量覆盖问题
        if isinstance(obj, np.floating):
            return round(float(obj),3)
        if isinstance(obj, np.integer):
            return int(obj)
        if obj.__class__.__name__ == 'datetime':
            return obj.isoformat()
        # 处理 NumPy 数值类型
        if hasattr(obj, "dtype") and hasattr(obj, "item"):
            return obj.item()  # 将 NumPy 数值转换为 Python 原生类型
        # 处理 bytes 类型
        if isinstance(obj, bytes):
            try:
                return obj.decode('utf-8')  # 尝试解码为 UTF-8 字符串
            except UnicodeDecodeError:
                # 如果解码失败，转换为十六进制字符串
                return obj.hex()
        return super().default(obj)

def trans_to_dict(obj):
    if hasattr(obj, "value") and not isinstance(obj, type):
        return obj.value
    # 使用类型名称字符串来检查，避免变量覆盖问题
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if obj.__class__.__name__ == 'datetime':
        return obj.isoformat()
    # 处理 NumPy 数值类型
    if hasattr(obj, "dtype") and hasattr(obj, "item"):
        return obj.item()  # 将 NumPy 数值转换为 Python 原生类型
    # 处理 bytes 类型
    if isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')  # 尝试解码为 UTF-8 字符串
        except UnicodeDecodeError:
            # 如果解码失败，转换为十六进制字符串
            return obj.hex()
    return obj

def trans_order_to_dict(row: Order,column_map) -> Order:
    
    return Order(
        order_id=row[column_map['order_id']],
        symbol=row[column_map['symbol']],
        direction=OrderSide(row[column_map['direction']]),
        price=row[column_map['price']],
        volume=row[column_map['volume']],
        status=OrderStatus(row[column_map['status']]),
        create_time=datetime.fromisoformat(row[column_map['create_time']]),
        filled_volume=row[column_map['filled_volume']],
        trader_platform=row[column_map['trader_platform']],
        is_active=bool(row[column_map['is_active']]),
        order_type=OrderType(row[column_map['order_type']]) if row[column_map['order_type']] else OrderType.MARKET,
        is_finished=bool(row[column_map['is_finished']]),
        strategy_name=row[column_map['strategy_name']],
        traded_price=row[column_map['traded_price']],
        execution_strategy=row[column_map['execution_strategy']],
        parent_id=row[column_map['parent_id']]
    )


class DataStorage:
    """数据存储类，负责订单和事件的持久化"""
    def __init__(self, db_path: str = "trading_data.db"):
        # 确保数据目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()
        self._migrate_db()  # 添加迁移步骤
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建订单表（如果不存在）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                symbol TEXT,
                direction TEXT,
                price REAL,
                volume REAL,
                status TEXT,
                create_time TEXT,
                filled_volume REAL,
                trader_platform TEXT,
                is_active INTEGER,
                order_type TEXT,
                is_finished INTEGER DEFAULT 0,
                strategy_name TEXT,
                traded_price REAL,
                execution_strategy TEXT,
                parent_id TEXT
            )
        ''')
        
        # 创建事件日志表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            data TEXT,
            timestamp TEXT
        )
        ''')
        
        # 检查表结构
        cursor.execute('PRAGMA table_info(orders)')
        columns = cursor.fetchall()
        # print("订单表结构:")
        # for col in columns:
        #     print(f"  {col[1]} ({col[2]})")
        
        conn.commit()
        conn.close()

    def _migrate_db(self):
        """迁移数据库结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 检查是否需要添加新列
            cursor.execute('PRAGMA table_info(orders)')
            columns = {col[1] for col in cursor.fetchall()}
            
            # 添加缺失的列
            if 'trader_platform' not in columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN trader_platform TEXT')
            
            if 'is_active' not in columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN is_active INTEGER DEFAULT 0')
            
            if 'order_type' not in columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN order_type TEXT')
            
            if 'is_finished' not in columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN is_finished INTEGER DEFAULT 0')
            
            # 添加新的列
            if 'strategy_name' not in columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN strategy_name TEXT')
            
            if 'traded_price' not in columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN traded_price REAL')
            
            if 'execution_strategy' not in columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN execution_strategy TEXT')
            
            if 'parent_id' not in columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN parent_id TEXT')
            
            conn.commit()
            print("数据库迁移完成")
            
        except Exception as e:
            print(f"Migration error: {e}")
            conn.rollback()
        
        finally:
            conn.close()

    def _serialize_order(self, order: Order) -> dict:
        """序列化订单对象"""
        data = {
            'order_id': order.order_id,
            'symbol': order.symbol,
            'direction': order.direction.value,
            'price': order.price,
            'volume': order.volume,
            'status': order.status.value,
            'create_time': order.create_time.isoformat(),
            'filled_volume': order.filled_volume,
            'trader_platform': order.trader_platform,
            'is_active': 1 if order.is_active else 0,
            'order_type': order.order_type.value if order.order_type else None,
            # 'last_price': order.last_price,
            'is_finished': 1 if order.is_finished else 0,
            'strategy_name': order.strategy_name,
            'traded_price': order.traded_price,
            'execution_strategy': order.execution_strategy,
            'parent_id': order.parent_id
        }
        return data
    
    def save_order(self, order: Order):
        """保存订单信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:

            order_data = {k:trans_to_dict(v) for k,v in asdict(order).items()}
            order_data['price'] = round(order_data['price'],3)
            order_data['update_time'] = datetime.now().isoformat()
            
            cursor.execute('''
            INSERT OR REPLACE INTO orders (
                order_id, symbol, direction, price, volume,
                status, create_time, filled_volume,
                trader_platform, is_active, order_type,
                is_finished, strategy_name, traded_price, execution_strategy, parent_id
            ) VALUES (
                :order_id, :symbol, :direction, :price, :volume,
                :status, :create_time, :filled_volume,
                :trader_platform, :is_active, :order_type, 
                :is_finished, :strategy_name, :traded_price, :execution_strategy, :parent_id
            )
            ''', order_data)
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def save_event(self, event: Event):
        """保存事件信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 检查events表是否存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
            if not cursor.fetchone():
                # 如果表不存在，创建它
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    data TEXT,
                    timestamp TEXT
                )
                ''')
                conn.commit()
            
            # 使用自定义 JSON 编码器序列化事件数据
            data = event.data
        
            # 转换 NumPy 类型
            data_dict = asdict(data)
            for key, value in data_dict.items():
                if hasattr(value, "dtype") and hasattr(value, "item"):
                    data_dict[key] = value.item()
            
            event_data = json.dumps(data_dict, cls=EnumEncoder)
            # 只有当事件类型为ORDER且存在parent_id时才进行更新操作
            if (event.type == EventType.ORDER and data.parent_id) or (data.status == OrderStatus.CANCELLED.value):
                cursor.execute('''
                UPDATE events 
                SET data = ?, timestamp = ?
                WHERE event_type = ? 
                AND json_extract(data, '$.parent_id') = ?
                AND event_type = 'ORDER'  -- 确保只更新ORDER类型的事件
                ''', (
                    event_data,
                    event.timestamp.isoformat(),
                    event.type.value,
                    data.parent_id
                ))
                
                if cursor.rowcount == 0:
                    cursor.execute('''
                    INSERT INTO events (event_type, data, timestamp) 
                    VALUES (?, ?, ?)
                    ''', (
                        event.type.value,
                        event_data,
                        event.timestamp.isoformat()
                    ))
            else:
                # 对于其他类型的事件，直接插入
                cursor.execute('''
                INSERT INTO events (event_type, data, timestamp) 
                VALUES (?, ?, ?)
                ''', (
                    event.type.value,
                    event_data,
                    event.timestamp.isoformat()
                ))
            
            conn.commit()
        except Exception as e:
            print(f"保存事件失败: {e}")
            traceback.print_exc()
        finally:
            conn.close()
        
    def get_order(self, order_id: str) -> Optional[Order]:
        """获取订单信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
            
            # 获取列名
            column_names = [description[0] for description in cursor.description]
            # 创建列名到索引的映射
            column_map = {name: i for i, name in enumerate(column_names)}
            
            row = cursor.fetchone()
            
            if row:
                # 使用列名映射获取数据
                return trans_order_to_dict(row,column_map)
            
            return None
        
        except Exception as e:
            print(f"获取订单失败: {e}")
            traceback.print_exc()
            return None
        
        finally:
            conn.close()

    def get_active_orders(self) -> List[Order]:
        """获取当天的活动订单和已完成订单，按时间降序排列"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            today = datetime.now().date()
            start_time = datetime.combine(today, datetime.min.time())
            end_time = datetime.combine(today, datetime.max.time())
            
            # 首先检查数据库中的状态值
            cursor.execute('''
                SELECT DISTINCT status FROM orders
                WHERE create_time >= ? 
                AND create_time <= ?
            ''', (start_time.isoformat(), end_time.isoformat()))
            
            # statuses = cursor.fetchall()
            # print(f"数据库中的状态值: {statuses}")
            
            # 修改查询语句并打印参数
            query = '''
                SELECT * FROM orders 
                WHERE (is_active = 1 
                      OR is_finished = 1 
                      OR status = ?) 
                AND create_time >= ? 
                AND create_time <= ?
                ORDER BY create_time DESC
            '''
            params = (OrderStatus.CANCELLED.value, start_time.isoformat(), end_time.isoformat())
            # print(f"查询参数: {params}")
            
            cursor.execute(query, params)
            
            # 获取列名
            column_names = [description[0] for description in cursor.description]
            column_map = {name: i for i, name in enumerate(column_names)}
            
            rows = cursor.fetchall()
            # print(f"\n找到 {len(rows)} 条订单")
            
            # 打印每个订单的状态
            # for row in rows:
                # status_idx = column_map['status']
                # print(f"订单状态: {row[status_idx]}")
            
            orders = []
            for row in rows:
                try:
                    order = trans_order_to_dict(row, column_map)
                    orders.append(order)
                except Exception as e:
                    print(f"处理订单行时出错: {e}")
                    traceback.print_exc()
                    continue
            
            return orders
        
        except Exception as e:
            print(f"获取活动订单失败: {e}")
            traceback.print_exc()
            return []
        
        finally:
            conn.close()
    
    def get_order_history(self, start_time: datetime = None, end_time: datetime = None) -> List[Order]:
        """获取历史订单"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 如果没有指定时间范围，默认获取最近7天的订单
            if not start_time:
                start_time = datetime.now() - timedelta(days=7)
            if not end_time:
                end_time = datetime.now()
            
            query = '''
                SELECT * FROM orders 
                WHERE create_time >= ? 
                AND create_time <= ?
                ORDER BY create_time DESC
            '''
            
            cursor.execute(query, (start_time.isoformat(), end_time.isoformat()))
            
            # 获取列名
            column_names = [description[0] for description in cursor.description]
            # 创建列名到索引的映射
            column_map = {name: i for i, name in enumerate(column_names)}
            
            rows = cursor.fetchall()
            
            orders = []
            for row in rows:
                try:
                    # 使用列名映射获取数据
                    order = trans_order_to_dict(row,column_map)
                    orders.append(order)
                except Exception as e:
                    print(f"处理订单行时出错: {e}")
                    traceback.print_exc()
                    continue
            
            return orders
            
        except Exception as e:
            print(f"获取历史订单失败: {e}")
            traceback.print_exc()
            return []
            
        finally:
            conn.close()

    def clear_old_orders(self, days: int = 30):
        """清理指定天数之前的订单数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            cursor.execute('''
                DELETE FROM orders 
                WHERE create_time < ?
            ''', (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            print(f"已清理 {deleted_count} 条历史订单")
            
        except Exception as e:
            print(f"清理历史订单失败: {e}")
            conn.rollback()
            
        finally:
            conn.close() 