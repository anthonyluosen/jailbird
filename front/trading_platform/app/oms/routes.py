from flask import render_template, jsonify, current_app, request
from app.oms import bp
from flask_login import login_required
from flask_socketio import emit
from datetime import datetime
from app.oms.storage import DataStorage
import traceback
import os
from itertools import groupby
from operator import itemgetter
from app.oms.constant import Order, OrderStatus, OrderSide, OrderType, Event, EventType
import uuid
# 全局的交易系统实例
trading_system = None
main_engine = None

# 创建数据库连接
storage = DataStorage(os.getenv('TRADING_DATA_PATH'))

@bp.route('/orders')
@login_required
def orders_page():
    """订单管理页面"""
    # init_oms()
    return render_template('oms/orders.html')

@bp.route('/api/orders')
@login_required
def get_orders():
    """获取所有活动订单，对于相同parent_id的订单只返回成交量最大的那一个，然后按时间排序"""
    try:
        all_orders = []
        active_orders = storage.get_active_orders()
        print(f"从数据库获取到 {len(active_orders)} 个活动订单")
        
        # 首先将所有订单转换为字典形式
        for order in active_orders:
            order_data = {
                'order_id': order.order_id,
                'parent_id': getattr(order, 'parent_id', None),
                'symbol': order.symbol,
                'direction': order.direction.value,
                'price': order.price,
                'volume': order.volume,
                'status': order.status.value,
                'filled_volume': order.filled_volume,
                'create_time': order.create_time.isoformat(),
                'trader_platform': order.trader_platform,
                'is_active': order.is_active,
                'strategy_name': order.strategy_name,
                'execution_strategy': getattr(order, 'execution_strategy', None),
                'traded_price': getattr(order, 'traded_price', None)
            }
            all_orders.append(order_data)
        
        # 分组处理订单
        filtered_orders = []
        
        # 将有parent_id的订单和没有的分开处理
        orders_with_parent = [o for o in all_orders if o['order_id']]
        orders_without_parent = [o for o in all_orders if not o['order_id']]
        
        # 直接添加没有parent_id的订单
        filtered_orders.extend(orders_without_parent)
        
        # 按parent_id分组，找出每组中成交量最大的
        if orders_with_parent:
            # 按parent_id排序
            orders_with_parent.sort(key=lambda x: x['order_id'])
            
            # 按parent_id分组
            for parent_id, group in groupby(orders_with_parent, key=lambda x: x['order_id']):
                group_list = list(group)
                # 找出成交量最大的订单
                max_filled_order = max(group_list, key=lambda x: x['filled_volume'] or 0)
                filtered_orders.append(max_filled_order)
        
        # 对过滤后的订单按创建时间排序（降序，最新的订单在前面）
        sorted_filtered_orders = sorted(filtered_orders, key=lambda x: x['create_time'], reverse=True)
        return jsonify(sorted_filtered_orders)
    except Exception as e:
        print(f"获取订单失败: {e}{traceback.format_exc()}")
        return jsonify([])

@bp.route('/api/external-orders', methods=['POST'])
def receive_external_orders():
    """接收外部订单数据并保存到数据库"""
    try:
        print(f"\n接收到外部订单API请求，内容类型: {request.content_type}")
        # 获取JSON数据
        order_data = request.json
        print(f"解析的JSON数据: {order_data}")
        
        if not order_data:
            print("错误: 没有提供有效的订单数据")
            return "错误：没有提供有效的订单数据", 400
        
        # 如果是单个订单，转换为列表处理
        if not isinstance(order_data, list):
            order_data = [order_data]
        
        saved_orders = []
        for order_item in order_data:
            # 验证必要字段
            required_fields = ['order_id', 'symbol', 'direction', 'price', 'volume', 'status']
            if not all(field in order_item for field in required_fields):
                missing_fields = [field for field in required_fields if field not in order_item]
                print(f"警告: 订单缺少必要字段 {missing_fields}，跳过此订单")
                continue  # 跳过缺少必要字段的订单
            
            # 创建订单对象
            try:
                order = Order(
                    order_id=order_item.get('order_id'),
                    symbol=order_item.get('symbol'),
                    direction=OrderSide(order_item.get('direction')),
                    price=float(order_item.get('price')),
                    volume=float(order_item.get('volume')),
                    status=OrderStatus(order_item.get('status')),
                    create_time=datetime.fromisoformat(order_item.get('create_time', datetime.now().isoformat())),
                    filled_volume=float(order_item.get('filled_volume', 0)),
                    trader_platform=order_item.get('trader_platform', 'EXTERNAL'),
                    is_active=bool(order_item.get('is_active', True)),
                    order_type=OrderType(order_item.get('order_type', 'MARKET')),
                    is_finished=bool(order_item.get('is_finished', False)),
                    strategy_name=order_item.get('strategy_name', ''),
                    traded_price=float(order_item.get('traded_price', 0)) if order_item.get('traded_price') else None,
                    execution_strategy=order_item.get('execution_strategy', ''),
                    parent_id=order_item.get('parent_id', '')
                )
                
                # 保存订单到数据库
                storage.save_order(order)
                saved_orders.append(order_item.get('order_id'))
                print(f"成功保存订单: {order_item.get('order_id')}")
                
                # 记录事件
                event = Event(
                    event_type=EventType.ORDER_UPDATE,
                    data={"order_id": order.order_id},
                    timestamp=datetime.now()
                )
                storage.save_event(event)
                
            except (ValueError, TypeError) as e:
                print(f"处理订单数据错误: {str(e)}")
                continue
        
        # 返回JSON响应
        result = {
            "status": "success", 
            "message": f"成功保存 {len(saved_orders)} 个订单", 
            "saved_orders": saved_orders
        }
        print(f"API响应: {result}")
        return jsonify(result)
        
    except Exception as e:
        error_msg = f"接收外部订单数据失败: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({"status": "error", "message": str(e)}), 500





