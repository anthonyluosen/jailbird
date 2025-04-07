import requests
import json

def test_order_add():
    """测试添加订单API"""
    url = "http://127.0.0.1:8000/oms/api/order-add"
    
    # 构建请求数据
    data = {
        "order_id": "1234",
        "symbol": "000001",
        "price": 100,
        "volume": 200,
        "order_type": "LIMIT",
        "direction": "BUY",
        "traded_price": None,
        "filled_volume": 0,
        "status": "SUBMITTING",
        "trader_platform": "PlatformType.QMT.value",
        "is_active": True,
        "strategy_name": "策略二",
        "execution_strategy": "BasicStrategy",
        "parent_id": None,
        "create_time": "2025-04-07 10:00:00"
    }
    
    # 发送POST请求
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, data=json.dumps(data), headers=headers)
    
    # 打印响应结果
    print(f"状态码: {response.status_code}")
    # print(f"响应内容: {response.text}")
    
    return response

if __name__ == "__main__":
    test_order_add() 