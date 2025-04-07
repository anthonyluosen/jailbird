from flask import jsonify, request, current_app
from app.api import bp
import os
import json
from datetime import datetime
from pathlib import Path

class AccountDataManager:
    def __init__(self, data_folder):
        self.data_folder = Path(data_folder)
        self.accounts_dir = self.data_folder / 'accounts'
        self.accounts_dir.mkdir(parents=True, exist_ok=True)
    
    def save_account_data(self, account_id, data):
        """保存账户数据到JSON文件"""
        # 确保数据包含最后更新时间
        if 'last_update' not in data:
            data['last_update'] = datetime.now().isoformat()
            
        # 构建文件路径
        file_path = self.accounts_dir / f"{account_id}.json"
        
        # 保存数据
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    def get_account_data(self, account_id):
        """获取账户数据"""
        file_path = self.accounts_dir / f"{account_id}.json"
        if not file_path.exists():
            return None
            
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_all_accounts(self):
        """获取所有账户数据"""
        accounts = {}
        for file_path in self.accounts_dir.glob('*.json'):
            account_id = file_path.stem
            with open(file_path, 'r', encoding='utf-8') as f:
                accounts[account_id] = json.load(f)
        return accounts

# 创建全局账户数据管理器实例
account_manager = None

def get_account_manager():
    """获取或创建账户数据管理器实例"""
    global account_manager
    if account_manager is None:
        account_manager = AccountDataManager(current_app.config['DATA_FOLDER'])
    return account_manager

@bp.route('/account/positions/update', methods=['POST'])
def update_account_positions():
    """更新账户持仓数据
    
    请求格式:
    {
        "account_id": "etf",  # 账户标识
        "data": {
            "total_assets": 99997.875,
            "cash": 64603.477,
            "market_value": 35394.4,
            "frozen_cash": 0.0,
            "positions": {
                "518880": {
                    "volume": 5000,
                    "cost": 35394.4,
                    "trade_price": 7.079,
                    "security_type": "ETF",
                    "unsellable_qty": 0,
                    "sellable_qty": 5000,
                    "latest_price": 2.0,
                    "market_value": 10000.0
                }
            },
            "trader_platform": "qmt",
            "initial_capital": 100000.0,
            "fees": 2.123664
        }
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({
                "status": "error",
                "message": "没有提供账户数据"
            }), 400
        
        # 验证必要字段
        if 'account_id' not in data or 'data' not in data:
            return jsonify({
                "status": "error",
                "message": "缺少必要字段：account_id 和 data"
            }), 400
        
        account_id = data['account_id']
        account_data = data['data']
        
        # 验证账户数据格式
        required_fields = ['total_assets', 'cash', 'market_value', 'positions']
        if not all(field in account_data for field in required_fields):
            return jsonify({
                "status": "error",
                "message": f"账户数据缺少必要字段: {', '.join(required_fields)}"
            }), 400
        
        # 保存账户数据
        manager = get_account_manager()
        manager.save_account_data(account_id, account_data)
        
        return jsonify({
            "status": "success",
            "message": f"账户 {account_id} 数据更新成功",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"更新账户数据失败: {str(e)}"
        }), 500

@bp.route('/account/positions', methods=['GET'])
def get_account_positions():
    """获取账户持仓数据
    
    查询参数:
    - account_id: 账户ID（可选，如果不提供则返回所有账户数据）
    """
    try:
        manager = get_account_manager()
        account_id = request.args.get('account_id')
        
        if account_id:
            # 获取特定账户数据
            account_data = manager.get_account_data(account_id)
            if account_data is None:
                return jsonify({
                    "status": "error",
                    "message": f"账户 {account_id} 不存在"
                }), 404
                
            return jsonify({
                "status": "success",
                "data": account_data
            })
        else:
            # 获取所有账户数据
            accounts = manager.get_all_accounts()
            return jsonify({
                "status": "success",
                "data": accounts
            })
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"获取账户数据失败: {str(e)}"
        }), 500 