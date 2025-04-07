from flask import Blueprint

bp = Blueprint('api', __name__, url_prefix='/api')

from app.api import account_positions  # 导入账户持仓相关的模块 