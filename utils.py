# -*- coding: utf-8 -*-
'''
@author: Ye Shengnan
create: Jul 14, 2014
'''
import subprocess
import threading
import select
import time
import os
import sys
from copy import deepcopy

import log
logger = log.get_logger('utils')


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


def run_command(command, _dir=None):
    retcode = 0
    old_dir = os.getcwd()
    if _dir is not None:
        os.chdir(_dir)

    logger.info('call [%s] in [%s]' % (command, _dir))
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, shell=True)
    fn_stdout = proc.stdout.fileno()
    fn_stderr = proc.stderr.fileno()
    sets = [fn_stdout, fn_stderr]
    output_stdout = None
    output_stderr = None
    while True:
        ret = select.select(sets, [], [])
        for fd in ret[0]:
            if fd == fn_stdout:
                output_stdout = proc.stdout.readline()
                if output_stdout:
                    output_stdout = output_stdout.rstrip()
                    logger.debug('out %s' % (output_stdout, ))

            if fd == fn_stderr:
                output_stderr = proc.stderr.readline()
                if output_stderr:
                    output_stderr = output_stderr.rstrip()
                    logger.debug('err %s' % (output_stderr, ))

        retcode = proc.poll()
        if retcode != None:
            if not output_stderr and not output_stdout:
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

    if encoding is not None:
        jstr = jstr.decode(encoding).encode('utf8')
        if show_log:
            logger.debug('after decoding:%s' % jstr)

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
    return process_json(open(fullpath).read(), show_log, encoding)


# from https://www.xormedia.com/recursively-merge-dictionaries-in-python/
def dict_merge(a, b):
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
    for k, v in b.iteritems():
        if k in result and isinstance(result[k], dict):
                result[k] = dict_merge(result[k], v)
        else:
            result[k] = deepcopy(v)
    return result


# 返回一个新的dict，dict_merge(ret, a) = b
# config时，默认设置为a，合并修改后为b。保存时只保存ret，启动时dict_merge(ret, a)恢复
# 支持嵌套dict，list。但list中的字典无法被递归比较，list中只要item的hash值不同即认为不同。
def dict_diff(a, b):
    def _dict_diff(a, b):
        result = None
        for (k, v) in b.iteritems():
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

    result = dict()
    for (k, v) in b.iteritems():
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
