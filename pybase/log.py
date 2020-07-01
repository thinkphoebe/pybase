# -*- coding: utf-8 -*-
import copy
import json
import logging
import logging.handlers
import os
import sys
import threading

# =================================================================================================
# json日志
#   输出传入dict时自动转为json输出，format为format_str设置的
#   logging_json_file_name不为None时仅dict的日志写入该文件，format为format_json变量设置的

# =================================================================================================
logging_console = False

logging_file_name = None

logging_json_file_name = None  # json日志的输出文件，仅打印传入为dict时输出到该文件，用于日志搜集分析

logging_file_rotating_count = 10
logging_file_rotating_compress = False

# rotating by size
logging_file_rotating_size = 1024 * 1024 * 10

# rotating by time
logging_file_rotating_period = None  # S, M, H, D, W
logging_file_rotating_interval = 1

logging_level = logging.DEBUG

# format_str = '%(asctime)s[lv%(levelno)s] %(module)s.%(funcName)s,L%(lineno)d %(message)-80s| P%(process)d. %(threadName)s'
format_str = '%(asctime)s|l%(levelno)s|%(module)s.%(funcName)s,L%(lineno)d|%(message)-80s'
format_json = '{"timestamp": "%(asctime)s", "level": "%(levelno)s", "module": "%(module)s", ' \
              '"function": "%(funcName)s", "line": "%(lineno)d", "message": %(message)s}'

# =================================================================================================
# internal used
_configured = False
_handler_console = None
_handler_file = None
_handler_json_file = None

_loggers = dict()
_formatter = None
_formatter_json = None

_stdout_backup = None
_stderr_backup = None


# =================================================================================================
def _update_logger(logger):
    global _handler_console
    global _handler_file
    global _handler_json_file
    if not _configured:
        update_config()
    if _handler_console != None:
        logger.addHandler(_handler_console)
    if _handler_file != None:
        logger.addHandler(_handler_file)
    if _handler_json_file != None:
        logger.addHandler(_handler_json_file)
    logger.setLevel(logging_level)


def get_logger(name='unknown'):
    global _loggers
    if name not in list(_loggers.keys()):
        logger = logging.getLogger(name)
        _update_logger(logger)
        _loggers[name] = logger
    return _loggers[name]


def update_config():
    global _configured
    global _loggers
    global _handler_console
    global _handler_file
    global _handler_json_file
    global _formatter
    global _formatter_json

    if _stdout_backup is not None:
        sys.stdout = _stdout_backup
    if _stderr_backup is not None:
        sys.stderr = _stderr_backup

    for logger in list(_loggers.values()):
        if _handler_console != None:
            logger.removeHandler(_handler_console)
        if _handler_file != None:
            logger.removeHandler(_handler_file)
        if _handler_json_file != None:
            logger.removeHandler(_handler_json_file)

    _formatter = Formatter(format_str)
    _formatter_json = Formatter(format_json)

    if logging_console:
        _handler_console = logging.StreamHandler(sys.stderr)
        _handler_console.setFormatter(_formatter)
    else:
        _handler_console = None

    if logging_file_name:
        if not os.path.exists(os.path.dirname(logging_file_name)):
            os.makedirs(os.path.dirname(logging_file_name))

        if logging_file_rotating_count > 0:
            if logging_file_rotating_period is None:
                _handler_file = logging.handlers.RotatingFileHandler(logging_file_name, mode='a',
                    maxBytes=logging_file_rotating_size,
                    backupCount=logging_file_rotating_count)
            else:
                _handler_file = logging.handlers.TimedRotatingFileHandler(logging_file_name,
                    when=logging_file_rotating_period,
                    interval=logging_file_rotating_interval,
                    backupCount=logging_file_rotating_count)
            if logging_file_rotating_compress:
                _handler_file.rotator = CompressRotator
        else:
            _handler_file = logging.FileHandler(logging_file_name, mode='a')

        _handler_file.setFormatter(_formatter)
    else:
        _handler_file = None

    if logging_json_file_name:
        if not os.path.exists(os.path.dirname(logging_json_file_name)):
            os.makedirs(os.path.dirname(logging_json_file_name))

        if logging_file_rotating_count > 0:
            if logging_file_rotating_period is None:
                _handler_json_file = RotatingFileHandlerJson(logging_json_file_name, mode='a',
                    maxBytes=logging_file_rotating_size,
                    backupCount=logging_file_rotating_count)
            else:
                _handler_json_file = TimedRotatingFileHandlerJson(logging_json_file_name,
                    when=logging_file_rotating_period,
                    interval=logging_file_rotating_interval,
                    backupCount=logging_file_rotating_count)
            if logging_file_rotating_compress:
                _handler_file.rotator = CompressRotator
        else:
            _handler_json_file = logging.FileHandler(logging_json_file_name, mode='a')

        _handler_json_file.setFormatter(_formatter_json)
    else:
        _handler_json_file = None

    for logger in list(_loggers.values()):
        _update_logger(logger)

    _configured = True


# =================================================================================================
class _stream2logger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """

    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())


def redirect_sysout():
    if not logging_console and not logging_file_name:
        print('no handler configured')
        return

    # 备份，在update_config()时恢复，以免update_config()对应的logger被关闭时导致问题
    global _stdout_backup
    global _stderr_backup
    if _stdout_backup is None:
        _stdout_backup = sys.stdout
    if _stderr_backup is None:
        _stderr_backup = sys.stderr

    sys.stdout = _stream2logger(get_logger('stdout'), logging.INFO)
    sys.stderr = _stream2logger(get_logger('stderr'), logging.ERROR)


# =================================================================================================
def CompressRotator(source, dest):
    if not os.path.exists(source):
        return

    os.rename(source, dest)

    COMPRESSION_SUPPORTED = {}
    try:
        import bz2
        COMPRESSION_SUPPORTED['bz2'] = bz2.BZ2File
    except ImportError:
        pass
    try:
        import gzip
        COMPRESSION_SUPPORTED['gz'] = gzip.GzipFile
    except ImportError:
        pass
    try:
        import zipfile
        COMPRESSION_SUPPORTED['zip'] = zipfile.ZipFile
    except ImportError:
        pass

    if 'bz2' in COMPRESSION_SUPPORTED:
        compress_cls = COMPRESSION_SUPPORTED['bz2']
        file_ext = '.bz2'
    elif 'gzip' in COMPRESSION_SUPPORTED:
        compress_cls = COMPRESSION_SUPPORTED['gzip']
        file_ext = '.gz'
    elif 'zip' in COMPRESSION_SUPPORTED:
        compress_cls = COMPRESSION_SUPPORTED['zip']
        file_ext = '.zip'
    else:
        return

    def compress():
        with open(dest, 'rb') as logfile:
            with compress_cls(dest + file_ext, 'wb') as comp_log:
                comp_log.write(logfile.read())
        os.remove(dest)

    thrd = threading.Thread(target=compress)
    thrd.start()


class Formatter(object):
    def __init__(self, fmt):
        self._formater = logging.Formatter(fmt=fmt)

    def format(self, record):
        record = copy.copy(record)
        if isinstance(record.msg, dict):
            record.msg = json.dumps(record.msg, ensure_ascii=True, sort_keys=True)
            record.args = None

        return self._formater.format(record)


class RotatingFileHandlerJson(logging.handlers.RotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def filter(self, record):
        return isinstance(record.msg, dict)


class TimedRotatingFileHandlerJson(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def filter(self, record):
        return isinstance(record.msg, dict)
