import unittest
import os
import config


class TestConfig(unittest.TestCase):
    @staticmethod
    def _createConfig():
        c = config.Config("A: b\nB:\n  C: d")
        return c

    def test_direct(self):
        c = self._createConfig()
        self.assertEqual(c["A"], 'b')
        self.assertRaises(KeyError, lambda: c['f'])

    def test_get(self):
        c = self._createConfig()
        self.assertEqual(c.get('A'), 'b')
        self.assertEqual(c.get('f'), None)

    def test_nested(self):
        c = self._createConfig()
        self.assertEqual(c['B'].get('C'), 'd')


class TestFilesConfig(unittest.TestCase):
    CONFIG = """
    filesystem:
        files:
            a: /A/B/testabs
            b: testmap
            c: testdefault
        pathes:
            default: /C/D
            b: /E/F
        file-path-map:
            b: b
    """

    CONFIG_2 = """
    filesystem:
        files:
            a: nodefault
            b: exists
        pathes:
            x: /nothing
        file-path-map:
            b: x
    """

    REALTIVE_PATH = """
    filesystem:
        files:
            a: /A/B/testabs
            b: testmap
            c: testdefault
            d: ./testrelative
        pathes:
            default: /C/D
            b: /E/F
        file-path-map:
            b: b
    """

    DEFAULT_ONLY = """
    filesystem:
        files:
            a: testdefault
        pathes:
            default: /C
    """

    def _createConfig(self):
        return config.Config(self.CONFIG)

    def _createConfigFiles(self):
        return config.FileConfig(self._createConfig())

    def test_absolute_path(self):
        f = self._createConfigFiles()
        self.assertEqual(f['a'], '/A/B/testabs')

    def test_relative(self):
        c = config.Config(self.REALTIVE_PATH)
        self.assertRaises(config.ConfigException, lambda: config.FileConfig(c))
        # The filename must be set either by creating the Config from a file or exlicitly
        c.filename = __file__
        fc = config.FileConfig(c)
        f = os.path.abspath(os.path.join(os.path.dirname(c.filename), './testrelative'))
        self.assertEqual(fc['d'], f)

    def test_map(self):
        f = self._createConfigFiles()
        self.assertEqual(f['b'], '/E/F/testmap')

    def test_default_path(self):
        f = self._createConfigFiles()
        self.assertEqual(f['c'], '/C/D/testdefault')

    def test_nonexisting(self):
        f = self._createConfigFiles()
        self.assertRaises(KeyError, lambda: f['X'])

    def test_nodefault(self):
        f = config.FileConfig(config.Config(self.CONFIG_2))
        self.assertEqual(f['b'], '/nothing/exists')
        self.assertRaises(KeyError, lambda: f['a'])

    def test_default_only(self):
        f = config.FileConfig(config.Config(self.DEFAULT_ONLY))
        self.assertEqual(f['a'], '/C/testdefault')

