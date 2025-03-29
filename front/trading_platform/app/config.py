import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data', 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DATA_FOLDER = os.environ.get('DATA_PATH') or r'E:\quant\code\thisday'
    PERMANENT_SESSION_LIFETIME = timedelta(days=31) 
    
    # 日志目录配置
    LOG_FOLDER = r"E:\quant\code\recycle\logs"
    
    @staticmethod
    def init_app(app):
        # 确保日志目录存在
        os.makedirs(app.config['LOG_FOLDER'], exist_ok=True)
    