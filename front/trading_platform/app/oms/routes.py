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

@bp.route('/api/order-add', methods=['POST'])
def add_orders():
    """添加订单
    入参：
    {
        "order_id": 1111,
        "symbol": "000001",
        "price": 100,
        "volume": 200,
        "order_type": "OrderType.LIMIT",
        "direction": "OrderSide.BUY",
        "traded_price": "100",
        "filled_volume": "0",
        "status": "OrderStatus.SUBMITTING",
        "create_time": "datetime.now(timezone(timedelta(hours": "8)))",
        "trader_platform": "PlatformType.QMT.value",
        "is_active": "True",
        "strategy_name": "策略二",
        "execution_strategy: "BasicStrategy",
        "parent_id": "generate_order_id())"
    }
    
    """ 
    import uuid
    from .constant import Order
    from datetime import datetime, timezone, timedelta

    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    print('请求参数-------', data)
    order = Order(
        order_id=data.get('order_id'),
        symbol=data.get('symbol'),
        price=data.get('price'),
        volume=data.get('volume'),
        order_type=data.get('order_type'),
        direction=data.get('direction'),
        traded_price=data.get('traded_price'),
        filled_volume=data.get('filled_volume'),
        status=data.get('status'),
        create_time=datetime.now(timezone(timedelta(hours=8))),
        trader_platform=data.get('trader_platform'),
        is_active=data.get('is_active'),
        strategy_name=data.get('strategy_name') ,
        execution_strategy=data.get('execution_strategy'),
        parent_id=uuid.uuid4().hex[:16]
    )

    try:
        conn = sqlite3.connect(storage.db_path)
        cursor = conn.cursor()

        from dataclasses import asdict
        from .storage import trans_to_dict
        
        order_data = {k:trans_to_dict(v) for k,v in asdict(order).items()}

        
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
        return jsonify({'error': str(e)}), 500       
    finally:
        conn.close()

    return jsonify({'message': 'Order added successfully'}), 201


