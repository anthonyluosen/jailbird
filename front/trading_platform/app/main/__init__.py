from flask import Blueprint

bp = Blueprint('main', __name__)

from app.main import routes  # 暂时注释掉 errors 