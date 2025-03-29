import sys
import logging
import queue
import threading
from io import StringIO

class WebOutputHandler(logging.Handler):
    """将日志输出重定向到网页的处理器"""
    def __init__(self):
        super().__init__()
        self.output_queue = queue.Queue()
        self.formatter = logging.Formatter('[%(levelname)s] %(message)s')

    def emit(self, record):
        try:
            msg = self.formatter.format(record)
            self.output_queue.put(('log', msg))
        except Exception:
            self.handleError(record)

class OutputCapture:
    """捕获标准输出和标准错误"""
    def __init__(self, output_queue):
        self.output_queue = output_queue
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        self._buffer = []

    def write(self, text):
        if text:
            self._buffer.append(text)
            if '\n' in text:
                self.flush()
            if self._stdout:
                self._stdout.write(text)

    def flush(self):
        if self._buffer:
            text = ''.join(self._buffer).rstrip()
            if text:
                self.output_queue.put(('print', text))
            self._buffer = []
        if self._stdout:
            self._stdout.flush()

class StderrCapture(OutputCapture):
    def write(self, text):
        if text:
            self._buffer.append(text)
            if '\n' in text:
                self.flush()
            if self._stderr:
                self._stderr.write(text)

    def flush(self):
        if self._buffer:
            text = ''.join(self._buffer).rstrip()
            if text:
                self.output_queue.put(('error', text))
            self._buffer = []
        if self._stderr:
            self._stderr.flush()

def setup_output_capture():
    """设置输出捕获"""
    handler = WebOutputHandler()
    logger = logging.getLogger()
    logger.addHandler(handler)
    
    # 捕获标准输出和标准错误
    output_capture = OutputCapture(handler.output_queue)
    stderr_capture = StderrCapture(handler.output_queue)
    
    # 保存原始的stdout和stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    # 替换stdout和stderr
    sys.stdout = output_capture
    sys.stderr = stderr_capture
    
    return handler.output_queue, (old_stdout, old_stderr)

def restore_output(original_streams=None):
    """恢复标准输出"""
    if original_streams:
        old_stdout, old_stderr = original_streams
        sys.stdout = old_stdout
        sys.stderr = old_stderr 