# -*- coding: utf-8 -*-
'''
@author: Ye Shengnan
create: Jul 22, 2014
'''
import json
import os

from . import log
from . import utils

import pybase.utils
import pybase.log
logger = log.get_logger('config')


class config(object):
    def __init__(self, default_file, user_file=None):
        logger.debug('default_file:%s, user_file:%s' % (default_file, user_file))
        self._default_file = utils.get_full_path(default_file)

        self._user_file = None
        if user_file is not None:
            self._user_file = utils.get_full_path(user_file)
        logger.debug('final default:%s, user:%s' % (self._default_file, self._user_file))

        self.data = dict()
        self.reload()

    def reload(self):
        logger.info('reload, default:%s, user:%s' % (self._default_file, self._user_file))

        self.data = json.loads(utils.read_json(self._default_file, show_log=True))
        logger.debug('default_loaded:%s', json.dumps(self.data, indent=2))

        if self._user_file is None and 'default' in self.data and 'user_file' in self.data['default']:
            full = utils.get_full_path(self.data['default']['user_file'])
            logger.warning('no user_file specified, get from default file: %s' % full)
            self._user_file = full

        if self._user_file is not None:
            try:
                user = json.loads(utils.read_json(self._user_file, show_log=True))
                logger.debug('user_loaded:%s', json.dumps(user, indent=2))
                self.data = utils.dict_merge(self.data, user)
                if 'default' not in self.data:
                    self.data['default'] = dict()
                if self._user_file is not None:
                    self.data['default']['user_file'] = self._user_file
            except:
                logger.exception('got execption on load user [%s]:' % self._user_file)
            logger.debug('final_merged:%s', json.dumps(self.data, indent=2))
        else:
            logger.debug('no user_file, use default_file only:%s', json.dumps(self.data, indent=2))

    def save(self):
        if self._user_file is None:
            logger.info('no user_file, can not save')
            return False

        ori = json.loads(utils.read_json(self._default_file, show_log=False))
        diff = utils.dict_diff(ori, self.data)

        logger.info('save config diff:%s, %s' % (self._user_file, json.dumps(diff, indent=2)))
        user_str = json.dumps(diff, indent=2)

        if not os.path.exists(os.path.dirname(self._user_file)):
            os.makedirs(os.path.dirname(self._user_file))
        open(self._user_file, 'wb').write(user_str)
        return True

    def get_value(self, key, session='default', default=None):
        if session not in self.data or key not in self.data[session]:
            return default
        return self.data[session][key]

    def set_value(self, key, value, session='default'):
        if session not in self.data:
            self.data[session] = dict()
        self.data[session][key] = value

    def have_value(self, key, session='default'):
        if session not in self.data:
            return False
        if key not in self.data[session]:
            return False
        return True
