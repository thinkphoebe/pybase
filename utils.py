# -*- coding: utf-8 -*-
'''
@author: Ye Shengnan
create: Jul 14, 2014
'''
import subprocess
import threading
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

    thrd_run = ThreadRun()
    thrd_run.start()
    while not thrd_run.complete and timeout > 0:
        time.sleep(0.1)
        timeout -= 0.1
    try:
        thrd_run.process.kill()
        thrd_run.process.wait()
        thrd_run.output[2] = True
    except:
        logger.exception('got exception:')

    return thrd_run.output


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


def read_json(fullpath, show_log=False):
    '''read json file and remove comments'''
    lines = open(fullpath).readlines()
    if show_log:
        logger.debug('original %s: %s' % (fullpath, ''.join(lines)))

    for line in lines[:]:
        line_lstrip = line.lstrip()
        if line_lstrip.startswith('//'):
            lines.remove(line)
    if show_log:
        logger.debug('after remove comments %s: %s' % (fullpath, ''.join(lines)))

    return ''.join(lines)


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
