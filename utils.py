# -*- coding: utf-8 -*-
'''
@author: Ye Shengnan
create: Jul 14, 2014
'''
import os
import select
import socket
import struct
import subprocess
import sys
import threading
import time
from copy import deepcopy

from . import log

logger = log.get_logger('utils')


class ExecptionMsg(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def check_output_timeout(url, timeout=10):
    class ThreadRun(threading.Thread):
        def __init__(self):
            super(ThreadRun, self).__init__()
            self.setName('check_output')
            self.complete = False
            self.output = [None, 0, False]  # output, return code, killed

        def run(self):
            self.process = subprocess.Popen(url, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
            output, unused_err = self.process.communicate()
            retcode = self.process.poll()
            if retcode:
                self.output[1] = retcode
            self.output[0] = output
            self.complete = True

    try:
        thrd_run = ThreadRun()
        thrd_run.start()
        while not thrd_run.complete and timeout > 0:
            time.sleep(0.1)
            timeout -= 0.1
    except (OSError, AttributeError):
        logger.exception('got exception:')

    try:
        thrd_run.process.kill()
        thrd_run.process.wait()
        thrd_run.output[2] = True
    except (OSError, AttributeError):
        #         logger.exception('got exception:')
        pass

    return thrd_run.output


class subprocess_logreader():
    def __init__(self, proc):
        self._proc = proc
        self._fn_stdout = proc.stdout.fileno()
        self._fn_stderr = proc.stderr.fileno()
        self._sets = [self._fn_stdout, self._fn_stderr]

    def read_log(self):
        # ATTENTION stdout如果被调用程序里没有调用fflush(stdout)，会一直读不到，直到程序退出时？
        output_stdout = None
        output_stderr = None
        _log = list()
        retcode = None

        while True:
            ret = select.select(self._sets, [], [])
            for fd in ret[0]:
                if fd == self._fn_stdout:
                    output_stdout = self._proc.stdout.readline()
                    if output_stdout:
                        output_stdout = output_stdout.rstrip()
                        _log.append((0, output_stdout))

                if fd == self._fn_stderr:
                    output_stderr = self._proc.stderr.readline()
                    if output_stderr:
                        output_stderr = output_stderr.rstrip()
                        _log.append((1, output_stderr))

            code = self._proc.poll()
            if code != None:
                if not output_stderr and not output_stdout:
                    retcode = code
            if len(_log) > 0 or ret is not None:
                break

        return (_log, retcode)


def run_command(command, _dir=None, log_id=None):
    retcode = 0
    old_dir = os.getcwd()
    if _dir is not None:
        os.chdir(_dir)

    logger.info('call [%s] in [%s]' % (command, _dir))
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, shell=True)
    logreader = subprocess_logreader(proc)
    while True:
        ret = logreader.read_log()
        for item in ret[0]:
            logger.debug('%s%s %s' % (log_id + '|' if log_id else '', 'out' if item[0] == 0 else 'err', item[1]))
        if ret[1] is not None:
            retcode = ret[1]
            break

    if _dir is not None:
        os.chdir(old_dir)
    return retcode


def getpwd():
    pwd = sys.path[0]
    if os.path.isfile(pwd):
        pwd = os.path.dirname(os.path.realpath(pwd))
    return pwd


def get_full_path(path):
    base_dir = getpwd()
    # ATTENTION: 在windows下先expanduser时，${}写法的环境变量会导致出错，如：
    # >>> print os.path.expanduser('~')
    # C:\Documents and Settings\Administrator
    # >>> print os.path.expanduser('~${OSSEP}.encng_manager${OSSEP}config')
    # C:\Documents and Settings\${OSSEP}.encng_manager${OSSEP}config
    # linux下未测试是否会有类似的问题
    path = os.path.expandvars(path)
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = base_dir + os.sep + path
    return path


def process_json(jstr, show_log=False, encoding=None):
    if show_log:
        logger.debug('original: %s' % jstr)

    if encoding is None:
        jstr = jstr.decode('utf-8')
    else:
        jstr = jstr.decode(encoding)
    if show_log:
        logger.debug('after decoding:%s' % jstr)
    jstr = str(jstr)

    # 下面代码，值中有单引号的情况会出错，暂不使用。
    # 处理json文件name没有加引号和值用单引号分割的情况。
    # 替换规则：以{[,开头后面可跟空白符，然后至少一个字母，后面任意个字母或数字，
    # 后面再任意的空白符，之后一个冒号。先加上''，再替换为""
    # jstr = re.sub(r"([\{\[,]\s*)([A-Za-z]+\w*?)\s*:", r"\1'\2' :", jstr)
    # jstr = jstr.replace("'", "\"")

    # 去掉//和/**/的注释，不支持注释和代码在一行内混合的情况。
    lines = jstr.split('\n')
    for line in lines[:]:
        line_strip = line.strip()
        if line_strip.startswith('//'):
            lines.remove(line)
        if line_strip.startswith('/*') and line_strip.endswith('*/'):
            lines.remove(line)

    if show_log:
        logger.debug('after remove comments:%s' % '\n'.join(lines))

    return '\n'.join(lines)


def read_json(fullpath, show_log=False, encoding=None):
    return process_json(open(fullpath, 'rb').read(), show_log, encoding)


# from https://www.xormedia.com/recursively-merge-dictionaries-in-python/
def dict_merge(a, b, hackerdel=True):
    '''recursively merges dict's. not just simple a['key'] = b['key'], if
    both a and bhave a key who's value is a dict then dict_merge is called
    on both values and the result stored in the returned dictionary.'''

    '''another solution
    http://stackoverflow.com/questions/3232943/update-value-of-a-nested-dictionary-of-varying-depth
    import collections
    def dict_merge(d, u):
        for k, v in u.iteritems():
            if isinstance(v, collections.Mapping):
                r = dict_merge(d.get(k, {}), v)
                d[k] = r
            else:
                d[k] = u[k]
        return d
    '''

    if not isinstance(b, dict):
        return b
    result = deepcopy(a)
    for k, v in b.items():
        if hackerdel and k.startswith('hackerdel_'):
            if k[len('hackerdel_'):] in result:
                logger.debug('remove key: %s' % k[len('hackerdel_'):])
                del result[k[len('hackerdel_'):]]
        elif k in result and isinstance(result[k], dict):
            result[k] = dict_merge(result[k], v)
        else:
            # ATTENTION: 此做法似乎“字典->列表->字典”情况时，列表内部的字典无法被merge
            result[k] = deepcopy(v)
    return result


# 返回一个新的dict，dict_merge(a, ret) = b
# config时，默认设置为a，合并修改后为b。保存时只保存ret，启动时dict_merge(a, ret)恢复
# 支持嵌套dict，list。但list中的字典无法被递归比较，list中只要item的hash值不同即认为不同。
def dict_diff(a, b, hackerdel=True):
    def _dict_diff(a, b):
        result = None
        for (k, v) in b.items():
            if k in a:
                if isinstance(v, (dict, tuple)):
                    ret = _dict_diff(a[k], v)
                    if ret is not None:
                        if result is None:
                            result = dict()
                        result[k] = ret
                elif isinstance(v, list):
                    ret = _list_diff(a[k], v)
                    if ret is not None:
                        if result is None:
                            result = dict()
                        result[k] = ret
                else:
                    if v != a[k]:
                        if result is None:
                            result = dict()
                        result[k] = v
            else:
                if result is None:
                    result = dict()
                result[k] = v
        return result

    def _list_diff(a, b):
        result = None
        for item in b:
            if item not in a:
                if result is None:
                    result = list()
                result.append(item)
        return result

    def _update_hacker_del(a, b):
        if not hackerdel:
            return
        for (k, v) in a.items():
            if k not in b:
                logger.debug('add hacker delete for key: %s' % k)
                b['hackerdel_' + k] = None
            elif isinstance(v, (dict, tuple)):
                _update_hacker_del(v, b[k])

    b = deepcopy(b)
    _update_hacker_del(a, b)

    result = dict()
    for (k, v) in b.items():
        if k in a:
            if isinstance(v, (dict, tuple)):
                ret = _dict_diff(a[k], v)
                if ret is not None:
                    result[k] = ret
            elif isinstance(v, list):
                ret = _list_diff(a[k], v)
                if ret is not None:
                    result[k] = ret
            else:
                if v != a[k]:
                    result[k] = v
        else:
            result[k] = v

    return result


def is_multicast_addr(addr_str):
    try:
        return socket.ntohl(struct.unpack('I', socket.inet_aton(addr_str))[0]) & 0xF0000000 == 0xE0000000
    except (socket.error, ValueError, IndexError):
        return False

def get_host_ip():
    ip = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip
