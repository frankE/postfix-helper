import unittest
import importlib
import textwrap
import sys
import os
import postfixhelper
import help

DATA = """#A file comment

#alias comment
alias1@domain           user1@domain
Multiline
  
 isAlsoPossible
alias2@domain           user1@domain
#== A system comment
  # A comment 
alias3@domain           user2@domain
#-- deleted             user2@domain
#comment at the end"""

FAULTY_DATA1 = """
alias1@domain           user1@domain
asdf
alias2@domain           user1@domain
  # A comment 
alias3@domain           user2@domain
"""

FAULTY_DATA2 = """
alias1@domain           user1@domain
asdf

asdf
alias2@domain           user1@domain
  # A comment 
alias3@domain           user2@domain
"""

NO_COMMENT = "abcde fghij"

EMPTY_CONFIG = './tests/testdata/emptyconfig.yaml'


def load_test_config():
    postfixhelper.load_file_config(config_file='./tests/testdata/testconfig.yaml')


def unload_config():
    if postfixhelper.CONFIG and postfixhelper.CONFIG.filename == EMPTY_CONFIG:
        for f in postfixhelper.FILE_CONFIG.values():
            if os.path.exists(f):
                os.remove(f)

    # Since there are module an class level variables we have to reload the whole module
    # It's a bit messy but ¯\_(ツ)_/¯
    importlib.reload(postfixhelper)


def load_empty_config():
    fc = postfixhelper.load_file_config(config_file=EMPTY_CONFIG)
    unload_config()
    fc = postfixhelper.load_file_config(config_file=EMPTY_CONFIG)
    for f in fc.values():
        with open(f, 'x') as file:
            print('', file=file)


class TestPostfixTableParser(unittest.TestCase):
    def test_read(self):
        data = postfixhelper.PostfixTableParser().parse(DATA)
        self.assertEqual(data['#'], postfixhelper.TableEntry(None, ['A file comment'], 0))
        self.assertEqual(data['alias1@domain'], postfixhelper.TableEntry('user1@domain', ['alias comment'], 4))
        self.assertEqual(data['Multiline'], postfixhelper.TableEntry('isAlsoPossible', [], 7))
        self.assertEqual(data['alias2@domain'], postfixhelper.TableEntry('user1@domain', [], 8))
        self.assertEqual(data['alias3@domain'], postfixhelper.TableEntry('user2@domain', ['A comment'], 11))
        self.assertEqual(data['deleted'], postfixhelper.TableEntry('user2@domain', [], 12, True))
        self.assertEqual(data[None], postfixhelper.TableEntry(None, ['comment at the end'], 13))

    def test_syntax_error(self):
        self.assertRaises(postfixhelper.ParserError, lambda: postfixhelper.PostfixTableParser().parse(FAULTY_DATA1))
        self.assertRaises(postfixhelper.ParserError, lambda: postfixhelper.PostfixTableParser().parse(FAULTY_DATA2))

    def test_no_comment(self):
        data = postfixhelper.PostfixTableParser().parse(NO_COMMENT)
        self.assertEqual(data['abcde'], postfixhelper.TableEntry('fghij', [], 1))
        self.assertRaises(KeyError, lambda: data[None])


class TestPFConfigurationFactory(unittest.TestCase):
    def setUp(self):
        load_test_config()

    def tearDown(self):
        unload_config()

    def test_create(self):
        alias = postfixhelper.PFAliasConfig()
        self.assertIsInstance(alias, postfixhelper.PFAliasConfig)
        self.assertIsNone(alias.get_alias('yuiop').sender)
        self.assertIsNotNone(alias.get_alias('alias@localdomain').sender.value)


class TestPFAlias(unittest.TestCase):
    @staticmethod
    def create_pf_alias():
        load_empty_config()
        return postfixhelper.PFAliasConfig()

    def setUp(self):
        self.alias = self.create_pf_alias()
        self.users = postfixhelper.PostfixTable('virtual-mailbox-users')
        self.users['testuser@localdomain'] = postfixhelper.TableEntry()

    def tearDown(self):
        unload_config()

    def test_create_alias(self):
        self.alias.add_alias('testalias@localdomain', 'testuser@localdomain', "comment")
        self.assertEqual(self.alias._virtual_alias['testalias@localdomain'],
                         postfixhelper.TableEntry('testuser@localdomain', ["comment"], sys.maxsize))

    def test_delete_alias(self):
        self.alias.add_alias('testalias@localdomain', 'testuser@localdomain', "comment")
        self.assertEqual(self.alias._virtual_alias['testalias@localdomain'],
                         postfixhelper.TableEntry('testuser@localdomain', ["comment"], sys.maxsize))
        self.alias.delete_alias('testalias@localdomain')
        self.assertRaises(KeyError, lambda: self.alias._sender_login_maps['testalias@localdomain'])

    def test_get_alias(self):
        a = self.alias.get_alias('alias@localdomain')
        expected = postfixhelper.Alias('alias@localdomain', None, None)
        self.assertEqual(expected.alias, a.alias)
        self.assertEqual(expected.sender, a.sender)
        self.assertEqual(expected.inbox, a.inbox)
        a = self.alias.get_alias('#')        # File comment
        expected = postfixhelper.Alias('#', postfixhelper.TableEntry(), postfixhelper.TableEntry())
        self.assertEqual(expected.alias, a.alias)
        self.assertEqual(expected.sender, a.sender)
        self.assertEqual(expected.inbox, a.inbox)

    def test_alias_without_user(self):
        self.assertRaises(postfixhelper.ConfigError, lambda: self.alias.add_alias('testalias@localdomain',
                                                                                  'nonexisting_user@localdomain'))


class TestPostfixTableSerializer(unittest.TestCase):
    def test_serialize(self):
        ser = postfixhelper.PFTableSerializer()
        data = {
            '#': postfixhelper.TableEntry(None, ['file comments', 'even with a second line'], 0),
            'key': postfixhelper.TableEntry('value', ['comments'], 4, True),
            'key2': postfixhelper.TableEntry('value', [], 5),
            'key3': postfixhelper.TableEntry('value2', [], 7),
        }
        expected = textwrap.dedent("""\
        # file comments
        # even with a second line
        
        #== Entries for value 'value'
        # comments
        #-- key         value
        key2            value
        
        #== Entries for value 'value2'
        key3            value2
        """)
        out = ser.serialize(data)
        self.assertEqual(out, expected)


class TestPostfixTable(unittest.TestCase):
    def setUp(self):
        load_empty_config()

    def tearDown(self):
        unload_config()

    def test_singleton_pattern(self):
        a1 = postfixhelper.PostfixTable('virtual-alias')
        a2 = postfixhelper.PostfixTable('virtual-alias')
        b = postfixhelper.PostfixTable('sender-login-maps')
        # Ensure no table has the test entry
        self.assertRaises(KeyError, lambda: a1['testvar1'])
        self.assertRaises(KeyError, lambda: a2['testvar1'])
        self.assertRaises(KeyError, lambda: b['testvar1'])
        # Insert data into one table only
        a1['testvar1'] = postfixhelper.TableEntry('testuser1', [], 999)
        # Both instances of the same table must hold the same data
        self.assertEqual(a1['testvar1'], postfixhelper.TableEntry('testuser1', [], 999))
        self.assertEqual(a2['testvar1'], postfixhelper.TableEntry('testuser1', [], 999))
        # The other table must not
        self.assertRaises(KeyError, lambda: b['testvar1'])


class TestApp(unittest.TestCase):
    def setUp(self):
        load_empty_config()
        self.app = postfixhelper.App()
        self.parser = postfixhelper.create_args_parser(help.Help)
        self.list_alias = self.parser.parse_args('alias list'.split(' '))
        self.users = postfixhelper.PostfixTable('virtual-mailbox-users')
        self.users['testsender'] = postfixhelper.TableEntry()
        self.users['testsender1'] = postfixhelper.TableEntry()

    def tearDown(self):
        unload_config()

    def test_add_alias(self):
        out = self.app.list_aliases(self.list_alias)
        self.assertEqual(-1, out.find('testalias'))
        self.assertEqual(-1, out.find('testsender'))

        args = self.parser.parse_args('alias add testalias testsender'.split(' '))
        out = self.app.add_alias(args)
        self.assertGreater(out.find('testalias'), -1)
        self.assertGreater(out.find('testsender'), -1)

    def test_del_alias(self):
        self.test_add_alias()

        args = self.parser.parse_args('alias del testalias'.split(' '))
        out = self.app.delete_alias(args)
        self.assertEqual(out.find('testalias'), -1)
        self.assertEqual(out.find('testsender'), -1)

    def test_del_alias_comment(self):
        self.test_add_alias()

        args = self.parser.parse_args('alias del --comment-out testalias'.split(' '))
        out = self.app.delete_alias(args)
        self.assertGreater(out.find('testalias'), -1)
        self.assertGreater(out.find('# testsender'), -1)

    def test_del_alias_save(self):
        self.test_add_alias()
        args = self.parser.parse_args('alias del --save testalias'.split(' '))
        self.app.delete_alias(args)
        out = self.app.list_aliases(self.list_alias)
        self.assertEqual(out.find('testalias'), -1)
        self.assertEqual(out.find('testsender'), -1)

    def test_del_user_alias(self):
        args = self.parser.parse_args('alias add --save testalias1 testsender'.split(' '))
        self.app.add_alias(args)
        args = self.parser.parse_args('alias add --save testalias2 testsender'.split(' '))
        self.app.add_alias(args)
        args = self.parser.parse_args('alias add --save testalias3 testsender'.split(' '))
        self.app.add_alias(args)

        args = self.parser.parse_args('alias del testalias1'.split(' '))
        out = self.app.delete_alias(args)
        self.assertEqual(out.find('testalias1'), -1)

        args = self.parser.parse_args('alias deluser --save testsender'.split(' '))
        self.app.delete_alias_user(args)

        out = self.app.list_aliases(self.list_alias)
        self.assertEqual(out.find('testalias2'), -1)
        self.assertEqual(out.find('testalias3'), -1)
        self.assertEqual(out.find('testsender'), -1)
