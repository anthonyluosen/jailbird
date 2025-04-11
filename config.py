import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data', 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DATA_FOLDER = os.environ.get('DATA_PATH') or os.path.join(basedir, 'logs', 'thisday')
    PERMANENT_SESSION_LIFETIME = timedelta(days=31)
    
    # 统一日志目录配置
    LOG_FOLDER = os.environ.get('LOG_FOLDER') or os.path.join(basedir, 'logs')
    TRADING_DATA_PATH = os.environ.get('TRADING_DATA_PATH') or os.path.join(basedir, 'trading_data.db')
    JAILBIRD_DATA_PATH = os.environ.get('JAILBIRD_DATA_PATH') or os.path.join(basedir, 'account_data_path')
    
    @staticmethod
    def init_app(app):
        # 确保日志目录存在
        os.makedirs(app.config['LOG_FOLDER'], exist_ok=True)
        os.makedirs(app.config['DATA_FOLDER'], exist_ok=True) 