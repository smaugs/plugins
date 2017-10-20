#!/usr/bin/env python3
# -*- coding: utf8 -*-
#########################################################################
# Copyright 2016-       René Frieß                  rene.friess@gmail.com
#                       Martin Sinn                         m.sinn@gmx.de
#                       Bernd Meiners
#                       Christian Strassburg          c.strassburg@gmx.de
#########################################################################
#  Backend plugin for SmartHomeNG
#
#  This plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This plugin is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this plugin. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import cherrypy
import logging
import platform
import collections
import datetime
import pwd
import html
import os
import json
import subprocess
import sys
import threading

from jinja2 import Environment, FileSystemLoader

import lib.config
from lib.logic import Logics
from lib.utils import Utils

from lib.model.smartplugin import SmartPlugin

from .BackendCore import BackendCore
from .BackendSysteminfo import BackendSysteminfo
from .BackendItems import BackendItems
from .BackendLogics import BackendLogics
from .BackendPlugins import BackendPlugins

from .utils import *



class BackendServer(SmartPlugin):

    PLUGIN_VERSION='1.4.7'

    def my_to_bool(self, value, attr='', default=False):
        try:
            result = self.to_bool(value)
        except:
            result = default
            self.logger.error("BackendServer: Invalid value '"+str(value)+"' configured for attribute "+attr+" in plugin.conf, using '"+str(result)+"' instead")
        return result
    
#    def __init__(self, sh, port=None, threads=8, ip='', updates_allowed='True', user="admin", password="", hashed_password="", language="", developer_mode="no", pypi_timeout=5):
    def __init__(self, sh, updates_allowed='True', user="admin", password="", hashed_password="", language="", developer_mode="no", pypi_timeout=5):
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Backend.__init__')
        
        #================================================================================
        # Checking and converting parameters
        #
        self._user = user
        self._password = password
        self._hashed_password = hashed_password

        if self._password is not None and self._password != "" and self._hashed_password is not None and self._hashed_password != "":
            self.logger.warning("BackendServer: Both 'password' and 'hashed_password' given. Ignoring 'password' and using 'hashed_password'!")
            self._password = None

        if self._password is not None and self._password != "" and (self._hashed_password is None or self._hashed_password == ""):
            self.logger.warning("BackendServer: Giving plaintext password in configuration is insecure. Consider using 'hashed_password' instead!")
            self._hashed_password = None

        if (self._password is not None and self._password != "") or (self._hashed_password is not None and self._hashed_password != ""):
            self._basic_auth = True
        else:
            self._basic_auth = False
        self._sh = sh

#        language = language.lower()
        language = self._sh.get_defaultlanguage()
        if language != '':
            if not load_translation(language):
                self.logger.warning("BackendServer: Language '{0}' not found, using standard language instead".format(language))
        self.developer_mode =  self.my_to_bool(developer_mode, 'developer_mode', False)

        self.updates_allowed = self.my_to_bool(updates_allowed, 'updates_allowed', True)

        if self.is_int(pypi_timeout):
            self.pypi_timeout = int(pypi_timeout)
        else:
            self.pypi_timeout = 5
            if pypi_timeout is not None:
                self.logger.error("BackendServer: Invalid value '" + str(pypi_timeout) + "' configured for attribute 'pypi_timeout' in plugin.conf, using '" + str(self.pypi_timeout) + "' instead")



        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.logger.debug("BackendServer running from '{}'".format(current_dir))


        #================================================================================
        # Handling for module http (try/except to handle running in a core version that does not support modules)
        #
        self.classname = self.__class__.__name__
        try:
            self.mod_http = sh.get_module('http')
        except:
             self.mod_http = None
        if self.mod_http == None:
            self.logger.error('{0}: Module ''http'' not loaded - Abort loading of plugin {0}'.format(self.classname))
            return

#        self.logger.warning('BackendServer: Using module {} version {}: {}'.format( str( self.mod_http.shortname ), str( self.mod_http.version ), str( self.mod_http.longname ) ) )
        self.logger.info('{}: Using module {}'.format(self.classname, str( self.mod_http._shortname ), str( self.mod_http.version ), str( self.mod_http._longname ) ) )
        config = {
            '/': {
                'tools.auth_basic.on': self._basic_auth,
                'tools.auth_basic.realm': 'earth',
                'tools.auth_basic.checkpassword': self.validate_password,
                'tools.staticdir.root': current_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': os.path.join(current_dir, 'static')
            }
        }
        appname = 'backend'    # Name of the plugin
        plugin = self.__class__.__name__
        instance = self.get_instance_name()

        self.mod_http.register_webif(Backend(self, self.updates_allowed, language, self.developer_mode, self.pypi_timeout), 
                                     appname, 
                                     config, 
                                     plugin, instance,
                                     description='Administrationsoberfläche für SmartHomeNG',
                                     webifname='')


    def run(self):
        self.logger.debug("BackendServer: rest run")
        self.alive = True

    def stop(self):
        self.logger.debug("BackendServer: shutting down")
#        self._server.stop()
        #self._cherrypy.engine.exit()
        self.logger.debug("BackendServer: engine exited")
        self.alive = False

    def parse_item(self, item):
        pass

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        pass

    def validate_password(self, realm, username, password):
        if username != self._user or password is None or password == "":
            return False

        if self._hashed_password is not None:
            return Utils.check_hashed_password(password, self._hashed_password)
        elif self._password is not None:
            return password == self._password

        return False

    

class Backend(BackendCore, BackendSysteminfo, BackendItems, BackendLogics, BackendPlugins):

    env = Environment(loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__))+'/templates'))
    from os.path import basename as get_basename
    env.globals['get_basename'] = get_basename
    env.globals['is_userlogic'] = Logics.is_userlogic
    env.globals['_'] = translate
    
    blockly_plugin_loaded = None    # None = load state is unknown

    def __init__(self, backendserver=None, updates_allowed=True, language='', developer_mode=False, pypi_timeout = 5):
        self.logger = logging.getLogger(__name__)
        self._bs = backendserver
        self._sh = backendserver._sh
        self.language = language
        self.updates_allowed = updates_allowed
        self.developer_mode = developer_mode
        self.pypi_timeout = pypi_timeout

        self._sh_dir = self._sh.base_dir
        self.visu_plugin = None
        self.visu_plugin_version = '1.0.0'
        

    def html_escape(self, str):
        return html_escape(str)

