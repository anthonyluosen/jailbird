from flask import render_template, request, current_app, jsonify
from flask_login import login_required
from app.main import bp
from app.main.utils import get_folder_contents
from app.main.process_manager import ProcessManager
from datetime import datetime
import pytz
import os
from app.notes.models import Note
from app import db

# 创建全局进程管理器实例
process_manager = None

@bp.route('/')
@bp.route('/folder')
@login_required
def index():
    china_tz = pytz.timezone('Asia/Shanghai')
    current_time = datetime.now(china_tz).isoformat()

    base_folder = current_app.config['DATA_FOLDER']
    folder_path = request.args.get('path', base_folder)

    # 规范化路径，统一使用正斜杠
    base_folder = os.path.normpath(base_folder).replace('\\', '/')
    folder_path = os.path.normpath(folder_path).replace('\\', '/')
    print(base_folder,folder_path)
    # 更安全的路径验证
    try:
        # 使用 os.path.abspath 获取绝对路径
        abs_base_folder = os.path.abspath(base_folder)
        abs_folder_path = os.path.abspath(folder_path)
        
        # 将路径统一为正斜杠格式
        abs_base_folder = abs_base_folder.replace('\\', '/')
        abs_folder_path = abs_folder_path.replace('\\', '/')
        
        # 检查请求的路径是否是基础路径的子目录
        if not abs_folder_path.startswith(abs_base_folder):
            current_app.logger.warning(f"尝试访问非法路径: {folder_path}")
            return "非法访问路径！", 403
            
        # 检查路径是否存在
        if not os.path.exists(abs_folder_path):
            current_app.logger.warning(f"路径不存在: {folder_path}")
            return "路径不存在！", 404
            
    except Exception as e:
        current_app.logger.error(f"路径验证错误: {str(e)}")
        return "路径验证错误！", 400

    # 获取文件夹内容
    try:
        folders, file_names = get_folder_contents(abs_folder_path)
    except Exception as e:
        current_app.logger.error(f"获取文件夹内容失败: {str(e)}")
        folders, file_names = [], []

    # 读取文件内容
    files = []
    for txt_file in file_names:
        file_path = os.path.join(abs_folder_path, txt_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            files.append({
                'filename': txt_file.replace(".txt", ""),
                'content': content
            })
        except Exception as e:
            current_app.logger.error(f"读取文件失败: {file_path} - {str(e)}")
    
    # 获取笔记列表
    try:
        notes = Note.query.order_by(Note.timestamp.desc()).all()
    except Exception as e:
        current_app.logger.error(f"获取笔记失败: {str(e)}")
        notes = []

    return render_template('main/index.html',
                         current_time=current_time,
                         folder_path=folder_path,
                         base_folder=base_folder,
                         folders=folders,
                         files=files,
                         notes=notes)

@bp.route('/logs')
@login_required
def logs():
    """日志监控页面"""
    base_folder = current_app.config['LOG_FOLDER']
    folder_path = request.args.get('path', base_folder)
    
    # 规范化路径
    folder_path = os.path.normpath(folder_path).replace('\\', '/')
    try:
        # 验证路径安全性
        abs_base_folder = os.path.abspath(base_folder).replace('\\', '/')
        abs_folder_path = os.path.abspath(folder_path).replace('\\', '/')
        
        if not abs_folder_path.startswith(abs_base_folder):
            return "非法访问路径！", 403
            
        if not os.path.exists(abs_folder_path):
            # 创建日志文件夹（如果不存在）
            try:
                os.makedirs(abs_folder_path, exist_ok=True)
                current_app.logger.info(f"创建日志目录: {abs_folder_path}")
            except Exception as e:
                current_app.logger.error(f"无法创建日志目录: {str(e)}")
                return "无法创建日志目录！", 500
            
        # 递归获取所有日志文件
        log_files = []
        for root, _, files in os.walk(abs_folder_path):
            for file in files:
                if file.endswith(('.log', '.txt', '.out', '.err')):
                    # 获取相对于基础目录的路径
                    rel_path = os.path.relpath(root, abs_folder_path)
                    if rel_path == '.':
                        log_files.append(file)
                    else:
                        log_files.append(os.path.join(rel_path, file).replace('\\', '/'))
                
        # 按文件名排序
        log_files.sort()
        
        # 如果没有日志文件，创建一个示例日志
        if not log_files:
            try:
                example_log_path = os.path.join(abs_folder_path, 'system.log')
                with open(example_log_path, 'w', encoding='utf-8') as f:
                    f.write(f"系统日志初始化 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("日志监控系统就绪\n")
                log_files = ['system.log']
                current_app.logger.info(f"创建示例日志文件: {example_log_path}")
            except Exception as e:
                current_app.logger.error(f"无法创建示例日志: {str(e)}")
        
        current_app.logger.info(f"找到日志文件: {log_files}")
                
        return render_template('main/logs.html',
                             folder_path=folder_path,
                             base_folder=base_folder,
                             log_files=log_files)
                             
    except Exception as e:
        current_app.logger.error(f"访问日志目录失败: {str(e)}")
        return "访问日志失败！", 500

@bp.route('/api/logs/content')
@login_required
def get_log_content():
    """获取日志文件内容"""
    file_path = request.args.get('path')
    last_position = request.args.get('position', type=int, default=0)
    
    if not file_path:
        return jsonify({'error': '未指定文件路径'}), 400
        
    try:
        # 获取基础日志目录
        abs_base_folder = os.path.abspath(current_app.config['LOG_FOLDER'])
        
        # 正确处理文件路径
        # 首先从file_path中提取文件名，避免路径遍历攻击
        file_name = os.path.basename(file_path)
        
        # 构建绝对路径
        abs_file_path = os.path.join(abs_base_folder, file_name)
        
        current_app.logger.info(f"正在读取日志文件: {abs_file_path}")
        current_app.logger.info(f"基础目录: {abs_base_folder}")
        
        if not os.path.commonpath([abs_base_folder, abs_file_path]) == abs_base_folder:
            current_app.logger.error(f"非法访问路径: {abs_file_path}")
            return jsonify({'error': '非法访问路径'}), 403
            
        if not os.path.exists(abs_file_path):
            current_app.logger.error(f"文件不存在: {abs_file_path}")
            return jsonify({'error': '文件不存在'}), 404
            
        # 读取文件内容
        file_size = os.path.getsize(abs_file_path)
        new_content = ''
        
        if file_size > last_position:
            try:
                with open(abs_file_path, 'r', encoding='utf-8') as f:
                    f.seek(last_position)
                    new_content = f.read()
            except UnicodeDecodeError:
                # 如果UTF-8解码失败，尝试使用GBK编码
                with open(abs_file_path, 'r', encoding='gbk') as f:
                    f.seek(last_position)
                    new_content = f.read()
                    
            current_app.logger.info(f"读取了 {len(new_content)} 字节的新内容")
                
        return jsonify({
            'content': new_content,
            'position': file_size
        })
        
    except Exception as e:
        current_app.logger.error(f"读取日志失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/process/start', methods=['POST'])
@login_required
def start_processes():
    """启动进程管理器"""
    try:
        data = request.json
        start_time = data.get('start_time', '09:15')
        end_time = data.get('end_time', '17:30')
        print(start_time,end_time)
        global process_manager
        if process_manager is None:
            process_manager = ProcessManager()
        
        process_manager.set_schedule(start_time, end_time)
        process_manager.start_scheduled_processes()
        
        return jsonify({
            'status': 'success',
            'message': f'进程管理器已启动，运行时间: {start_time}-{end_time}'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/process/stop', methods=['POST'])
def stop_processes():
    """停止进程管理器"""
    try:
        global process_manager
        if process_manager:
            process_manager.stop_scheduled_processes()
            return jsonify({
                'status': 'success',
                'message': '进程管理器已停止'
            })
        return jsonify({
            'status': 'error',
            'message': '进程管理器未运行'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@bp.route('/process/status')
def get_process_status():
    """获取进程状态"""
    try:
        global process_manager
        if process_manager:
            return jsonify({
                'status': 'running' if process_manager.running else 'stopped',
                'schedule': process_manager.schedule,
                'is_trading_time': process_manager.is_trading_time()
            })
        return jsonify({
            'status': 'not_initialized'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 