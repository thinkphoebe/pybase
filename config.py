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


class config(object):
    '''
    __init__()时如指定user_path参数，则强制使用user_path参数指定的文件。 如未指定user_path参数，
    default_path的文件中必须包含"default/user_cfg_path"配置项，使用该参数指定的文件。
    '''

    def __init__(self, filename, default_path, user_path=None):
        logger.debug('filename:%s, default_path:%s, user_path:%s' % (filename, default_path, user_path))
        self._filename = filename
        self._default_file = utils.get_full_path(default_path + os.sep + filename)
        self._user_file = None
        if user_path is not None:
            self._user_file = utils.get_full_path(user_path + os.sep + filename)
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
            full = utils.get_full_path(self._data['default']['user_cfg_path'] + os.sep + self._filename)
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

    def have_value(self, key, session='default'):
        if session not in self._data:
            return False
        if key not in self._data[session]:
            return False
        return True
