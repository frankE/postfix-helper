#!/usr/bin/env python3
import os
import logging
import collections
from abc import ABC

import yaml

__all__ = ['Config', 'FileConfig', 'ConfigException']


class ConfigException(Exception):
    pass


class Config(collections.UserDict):
    def __init__(self, config=None, filename=None):
        super().__init__()
        self.filename = filename
        if config is not None:
            self.data = yaml.load(config, Loader=yaml.SafeLoader)
        elif filename is not None:
            try:
                self.data = self._load(filename)
            except Exception as e:
                raise ConfigException('Error loading configuration file %s.' % filename) from e
        else:
            raise ConfigException("No config or filename given.")

    @staticmethod
    def _load(filename):
        with open(filename) as f:
            d = yaml.load(f, Loader=yaml.SafeLoader)
        return d

    def dump(self):
        return yaml.dump(self.data, default_flow_style=False, indent=4)


class FileConfig(collections.abc.Mapping):
    def __init__(self, config):
        self._config = config
        self._pathes = {}
        self._init_pathes()

    def __len__(self) -> int:
        return len(self._pathes)

    def __iter__(self):
        return iter(self._pathes)

    def __getitem__(self, key):
        return self._pathes[key]

    def _set(self, name, path, file=None):
        if file is None:
            self._pathes[name] = os.path.expanduser(path)
        else:
            self._pathes[name] = os.path.join(os.path.expanduser(path), file)

    def _init_pathes(self):
        filesystem = self._config.get('filesystem')
        if filesystem is None:
            logging.warning("No filesystem entry in config %s" % self._config.filename)
            return

        files = filesystem.get('files')
        if files is None:
            logging.info("No files entry under 'filesystem' in config %s" % self._config.filename)
            return

        for name, file in files.items():
            if os.path.isabs(file) or file.startswith('~'):
                self._set(name, file)
            elif file.startswith('.'):
                if self._config.filename is None:
                    raise ConfigException("Can not handle relative pathes without a config file.")
                f = os.path.abspath(os.path.join(os.path.dirname(self._config.filename), file))
                self._set(name, os.path.abspath(f))
            else:
                path = self._get_path(filesystem, name)
                if path is not None:
                    self._set(name, path, file)
                else:
                    logging.info("Path for '%s' not found in configfile '%s'", name, self._config.filename)

    def _get_path(self, fscfg, name):
        pathmap = fscfg.get('file-path-map')
        pathes = fscfg.get('pathes')
        if pathes is None:
            logging.info("Couldn't find 'pathes' in config % s", self._config.filename)
            return None

        if pathmap is None:
            logging.info("Couldn't find 'file-path-map' in config %s", self._config.filename)
            return pathes.get('default')
        path_alias = pathmap.get(name)

        if path_alias is None:
            path = pathes.get('default')
        else:
            path = pathes.get(path_alias)

        return path
