from flask import render_template, jsonify, current_app
from app.oms import bp
from flask_login import login_required
from flask_socketio import emit
from datetime import datetime
from app.oms.storage import DataStorage
import traceback
import os
from itertools import groupby
from operator import itemgetter
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

