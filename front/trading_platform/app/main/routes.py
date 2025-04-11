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
import json
import csv
import math
import numpy as np
from collections import defaultdict

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

@bp.route('/trading_performance')
@login_required
def trading_performance():
    """账户交易数据展示页面"""
    # 基础路径设置
    base_folder = current_app.config.get('JAILBIRD_DATA_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'strategy_results'))

    backtest_folder = current_app.config.get('STRATEGY_RESULTS_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'strategy_results'))
    # 获取所有可用策略
    strategies = []
    try:
        for item in os.listdir(base_folder):
            if item.endswith('.json'):
                strategies.append(item.replace('.json', ''))
    except Exception as e:
        current_app.logger.error(f"读取策略列表失败: {str(e)}")
    
    # 获取所有日期文件夹
    dates = []
    try:
        for item in os.listdir(base_folder):
            if os.path.isdir(os.path.join(base_folder, item)) and item.startswith('20'):
                dates.append(item)
        # 按日期排序
        dates.sort()
    except Exception as e:
        current_app.logger.error(f"读取日期列表失败: {str(e)}")
    
    # 如果没有选择策略，默认选择第一个
    selected_strategy = request.args.get('strategy', strategies[0] if strategies else None)
    
    # 搜索回测结果目录，查找策略目录
    backtest_strategies = []
    backtest_data = {}
    backtest_metrics = {}
    
    try:
        # 搜索回测目录下的所有策略文件夹
        if os.path.exists(backtest_folder):
            for strategy_dir in os.listdir(backtest_folder):
                strategy_path = os.path.join(backtest_folder, strategy_dir)
                if os.path.isdir(strategy_path):
                    # 查找净值文件
                    nv_file = os.path.join(strategy_path, 'strategy_nv.csv')
                    if os.path.exists(nv_file):
                        backtest_strategies.append(strategy_dir)
                        
                        try:
                            # 读取净值文件
                            with open(nv_file, 'r', encoding='utf-8') as csvfile:
                                reader = csv.DictReader(csvfile)
                                data = list(reader)
                                
                                # 处理数据
                                dates_list = []
                                net_values = []
                                returns = []
                                drawdowns = []
                                
                                for row in data:
                                    if 'date' in row and 'net_value' in row:
                                        dates_list.append(row['date'])
                                        
                                        # 处理净值数据，确保非空
                                        net_value_str = row['net_value']
                                        try:
                                            if net_value_str and net_value_str.strip():
                                                net_values.append(float(net_value_str))
                                            else:
                                                # 如果净值为空，使用前一个值或默认值1.0
                                                last_value = net_values[-1] if net_values else 1.0
                                                net_values.append(last_value)
                                                current_app.logger.warning(f"策略{strategy_dir}在{row['date']}的净值为空，使用{last_value}")
                                        except ValueError:
                                            # 如果转换失败，使用前一个值或默认值1.0
                                            last_value = net_values[-1] if net_values else 1.0
                                            net_values.append(last_value)
                                            current_app.logger.warning(f"策略{strategy_dir}在{row['date']}的净值格式错误: {net_value_str}，使用{last_value}")
                                        
                                        # 处理收益率数据，确保非空
                                        return_str = row.get('return', '')
                                        try:
                                            if return_str and return_str.strip():
                                                returns.append(float(return_str))
                                            else:
                                                # 如果收益率为空，使用0.0
                                                returns.append(0.0)
                                        except ValueError:
                                            returns.append(0.0)
                                            current_app.logger.warning(f"策略{strategy_dir}在{row['date']}的收益率格式错误: {return_str}，使用0.0")
                                        
                                        # 处理回撤数据，确保非空
                                        drawdown_str = row.get('drawdown', '')
                                        try:
                                            if drawdown_str and drawdown_str.strip():
                                                drawdowns.append(float(drawdown_str))
                                            else:
                                                # 如果回撤为空，使用0.0
                                                drawdowns.append(0.0)
                                        except ValueError:
                                            drawdowns.append(0.0)
                                            current_app.logger.warning(f"策略{strategy_dir}在{row['date']}的回撤格式错误: {drawdown_str}，使用0.0")
                                
                                if not dates_list or not net_values:
                                    current_app.logger.warning(f"策略{strategy_dir}的净值文件格式不正确或为空")
                                    continue
                                
                                # 计算关键指标
                                # 1. 计算年化收益率
                                days = len(net_values)
                                annual_return = ((net_values[-1] / net_values[0]) ** (365/days) - 1) * 100 if days > 0 and net_values[0] > 0 else 0
                                
                                # 2. 计算最大回撤
                                max_drawdown = max(drawdowns) * 100 if drawdowns else 0
                                
                                # 3. 计算夏普比率 (假设无风险利率为0.03)
                                risk_free_rate = 0.03
                                if len(returns) > 1:
                                    daily_returns = np.array(returns)
                                    excess_returns = daily_returns - (risk_free_rate / 365)
                                    sharpe_ratio = np.sqrt(365) * np.mean(excess_returns) / np.std(excess_returns) if np.std(excess_returns) > 0 else 0
                                else:
                                    sharpe_ratio = 0
                                    
                                # 4. 计算波动率
                                volatility = np.std(returns) * np.sqrt(252) * 100 if returns else 0
                                
                                # 保存回测数据
                                backtest_data[strategy_dir] = {
                                    'dates': dates_list,
                                    'net_values': net_values,
                                    'returns': returns,
                                    'drawdowns': drawdowns
                                }
                                
                                # 计算胜率
                                if returns:
                                    win_count = sum(1 for r in returns if r > 0)
                                    win_ratio = (win_count / len(returns)) * 100 if len(returns) > 0 else 0
                                else:
                                    win_ratio = 0
                                
                                # 保存指标数据
                                backtest_metrics[strategy_dir] = {
                                    'annual_return': annual_return,
                                    'max_drawdown': max_drawdown,
                                    'sharpe_ratio': sharpe_ratio,
                                    'volatility': volatility,
                                    'total_return': (net_values[-1] / net_values[0] - 1) * 100 if net_values and net_values[0] > 0 else 0,
                                    'win_ratio': win_ratio,
                                }
                        except Exception as e:
                            current_app.logger.error(f"处理策略{strategy_dir}数据失败: {str(e)}")
                            continue
        
        # 按照名称排序策略列表
        backtest_strategies.sort()
        current_app.logger.info(f"找到{len(backtest_strategies)}个回测策略")
    except Exception as e:
        current_app.logger.error(f"读取回测数据失败: {str(e)}")
    
    # 如果直接在根目录有对应的策略文件，先读取它
    root_strategy_data = {}
    if selected_strategy:
        try:
            root_file_path = os.path.join(base_folder, f"{selected_strategy}.json")
            if os.path.exists(root_file_path):
                with open(root_file_path, 'r', encoding='utf-8') as f:
                    root_strategy_data = json.load(f)
        except Exception as e:
            current_app.logger.error(f"读取根目录策略数据失败: {str(e)}")
    
    # 收集策略的绩效数据
    performance_data = {}
    positions_data = {}
    
    # 首先检查是否有根目录数据，并提取持仓信息
    if root_strategy_data:
        positions_data = root_strategy_data.get('positions', {})
        
        # 如果只有根目录数据，也添加到性能数据中
        latest_date = datetime.now().strftime('%Y-%m-%d')
        performance_data[latest_date] = {
            'total_assets': root_strategy_data.get('total_assets', 0),
            'cash': root_strategy_data.get('cash', 0),
            'market_value': root_strategy_data.get('market_value', 0),
            'initial_capital': root_strategy_data.get('initial_capital', 100000),
            'returns': (root_strategy_data.get('total_assets', 0) / root_strategy_data.get('initial_capital', 100000)) - 1,
            'fees': root_strategy_data.get('fees', 0)
        }
        
    # 然后遍历所有日期文件夹，收集历史数据
    if selected_strategy and dates:
        for date in dates:
            try:
                file_path = os.path.join(base_folder, date, f"{selected_strategy}.json")
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # 收集净值数据
                        performance_data[date] = {
                            'total_assets': data.get('total_assets', 0),
                            'cash': data.get('cash', 0),
                            'market_value': data.get('market_value', 0),
                            'initial_capital': data.get('initial_capital', 100000),
                            'returns': (data.get('total_assets', 0) / data.get('initial_capital', 100000)) - 1,
                            'fees': data.get('fees', 0)
                        }
                        
                        # 如果还没有持仓数据或这是最新日期，更新持仓数据
                        if not positions_data and date == dates[-1]:
                            positions_data = data.get('positions', {})
            except Exception as e:
                current_app.logger.error(f"读取{date}日{selected_strategy}策略数据失败: {str(e)}")
    
    # 按日期排序
    performance_series = [
        {
            'date': date,
            'total_assets': data['total_assets'],
            'cash': data['cash'],
            'market_value': data['market_value'],
            'returns': data['returns'] * 100,  # 转为百分比
            'fees': data['fees']
        } for date, data in sorted(performance_data.items())
    ]
    
    current_app.logger.info(f"找到策略: {selected_strategy}, 日期: {len(dates)}, 性能数据: {len(performance_series)}, 持仓数据: {len(positions_data)}")
    
    # 处理持仓数据，确保每个持仓都有所有必要的字段
    processed_positions = {}
    if positions_data:  # 确保positions_data不是None
        for code, pos in positions_data.items():
            # 确保pos是字典类型
            if isinstance(pos, dict):
                processed_pos = {
                    'volume': pos.get('volume', 0),
                    'cost': pos.get('cost', 0),
                    'sellable_qty': pos.get('sellable_qty', pos.get('volume', 0)),
                    'unsellable_qty': pos.get('unsellable_qty', 0),
                    'trade_price': pos.get('trade_price', 0),
                    'latest_price': pos.get('latest_price', 0),
                    'market_value': pos.get('market_value', 0),
                    'security_type': pos.get('security_type', 'UNKNOWN')
                }
                processed_positions[code] = processed_pos
            else:
                current_app.logger.warning(f"持仓数据格式异常，代码: {code}, 数据: {pos}")
    
    current_app.logger.info(f"处理后的持仓数据: {len(processed_positions)} 个持仓")
    
    # 获取选择的回测策略
    selected_backtest_strategy = request.args.get('backtest_strategy', backtest_strategies[0] if backtest_strategies else None)
    selected_backtest_data = backtest_data.get(selected_backtest_strategy, {})
    selected_backtest_metrics = backtest_metrics.get(selected_backtest_strategy, {})
    
    return render_template('main/trading_performance.html',
                         strategies=strategies,
                         selected_strategy=selected_strategy,
                         performance_series=performance_series,
                         positions=processed_positions,
                         backtest_strategies=backtest_strategies,
                         selected_backtest_strategy=selected_backtest_strategy,
                         backtest_data=selected_backtest_data,
                         backtest_metrics=selected_backtest_metrics) 