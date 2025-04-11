import subprocess
import time
from datetime import datetime
import threading

class ProcessManager:
    def __init__(self):
        self.processes = {}
        self.running = True
        # self.logger = Logger("ProcessManager",logDir=r"F:\workspace\code\recycle")
        self.schedule = {
            'start_time': '09:15',  # 默认开始时间
            'end_time': '17:30'     # 默认结束时间
        }
        self.schedule_thread = None


    def set_schedule(self, start_time, end_time):
        """设置运行时间区间"""
        self.schedule['start_time'] = start_time
        self.schedule['end_time'] = end_time
        print(f"设置运行时间区间: {start_time} - {end_time}")

    def is_trading_time(self):
        """检查当前是否在交易时间内"""
        now = datetime.now().strftime('%H:%M')
        return self.schedule['start_time'] <= now <= self.schedule['end_time']

    def schedule_runner(self):
        """定时检查并管理进程"""
        while self.running:
            try:
                current_time = datetime.now().strftime('%H:%M')
                
                if self.is_trading_time():
                    # 如果在交易时间内且进程未运行，则启动进程
                    for name, command in self.process_commands.items():
                        if name not in self.processes or self.processes[name] is None or self.processes[name].poll() is not None:
                            self.start_process(name, command)
                else:
                    # 如果不在交易时间内，停止所有进程
                    self.stop_all()
                
                time.sleep(60)  # 每分钟检查一次
            except Exception as e:
                print(f"调度错误: {e}")

    def start_scheduled_processes(self):
        """启动调度线程"""
        if self.schedule_thread is None or not self.schedule_thread.is_alive():
            self.running = True
            self.schedule_thread = threading.Thread(target=self.schedule_runner)
            self.schedule_thread.daemon = True
            self.schedule_thread.start()
            print("启动调度线程")

    def stop_scheduled_processes(self):
        """停止调度"""
        self.running = False
        if self.schedule_thread:
            self.schedule_thread.join(timeout=2.0)
        self.stop_all()
        print("停止调度")

    def start_process(self, name, command):
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            self.processes[name] = process
            print(f"Started process {name}")
            return process
        except Exception as e:
            print(f"Error starting process {name}: {e}")
            return None

    def restart_process(self, name):
        if name in self.processes:
            self.stop_process(name)
            time.sleep(2)  # 等待进程完全停止
            command = self.processes[name].args
            self.start_process(name, command)
            print(f"Restarted process {name}")

    def stop_process(self, name):
        if name in self.processes:
            process = self.processes[name]
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            print(f"Stopped process {name}")

    def monitor_processes(self):
        while self.running:
            for name, process in self.processes.items():
                if process.poll() is not None:  # 进程已终止
                    print(f"Process {name} has died, restarting...")
                    self.restart_process(name)
            time.sleep(5)

    def stop_all(self):
        self.running = False
        for name in list(self.processes.keys()):
            self.stop_process(name)
