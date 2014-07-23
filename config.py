# -*- coding: utf-8 -*-
'''
@author: Ye Shengnan
create: Jul 22, 2014
'''
import os
import json

import utils
import log
logger = log.get_logger('config')


def _get_full_path(path):
    base_dir = utils.getpwd()
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    if not os.path.isabs(path):
        path = base_dir + os.sep + path
    return path


class config(object):
    '''
    __init__()时如指定user参数，则强制使用user参数指定的文件。
    如未指定user参数，default文件中必须包含"default/user_cfg_path"配置项，使用该参数指定的文件。
    '''

    def __init__(self, default, user=None):
        logger.debug('default:%s, user:%s' % (default, user))
        self._default_file = _get_full_path(default)
        self._user_file = None
        if user is not None:
            self._user_file = _get_full_path(user)
        logger.debug('final default:%s, user:%s' % (self._default_file, self._user_file))

        self._data = dict()
        self.reload()

    def reload(self):
        logger.info('reload, default:%s, user:%s' % (self._default_file, self._user_file))
        default_str = open(self._default_file).read()
        logger.debug('default_str:%s', default_str)

        self._data = json.loads(default_str)
        logger.debug('default_loaded:%s', json.dumps(self._data, indent=2))

        if self._user_file is None:
            full = _get_full_path(self._data['default']['user_cfg_path'])
            logger.warning('no user_file specified, get from default file: %s' % full)
            self._user_file = full

        try:
            user_str = open(self._user_file).read()
            logger.debug('user_str:%s', user_str)
            user = json.loads(user_str)
            logger.debug('user_loaded:%s', json.dumps(user, indent=2))
            self._data = utils.dict_merge(self._data, user)
        except:
            logger.exception('got execption on load user:')

        logger.debug('final_merged:%s', json.dumps(self._data, indent=2))

    def save(self):
        logger.info('save config:%s' % self._user_file)
        user_str = json.dumps(self._data, indent=2)
        if not os.path.exists(os.path.dirname(self._user_file)):
            os.makedirs(os.path.dirname(self._user_file))
        open(self._user_file, 'wb').write(user_str)

    def get_value(self, key, session='default'):
        return self._data[session][key]

    def set_value(self, key, value, session='default'):
        self._data[session][key] = value


if __name__ == '__main__':
    default = '''{
    "default": {
             "testkey": "test value",
             "testkey2": "test value2"
    }
}
'''
    open('/tmp/default.json', 'wb').write(default)
    cfg = config('/tmp/default.json', '/tmp/a/user.json')
    print 'value of testkey:', cfg.get_value(key='testkey')
    cfg.set_value(key='testkey', value='value modified')
    cfg.save()

    print open('/tmp/a/user.json').read()
