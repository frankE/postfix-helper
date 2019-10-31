#!/usr/bin/env python3
import re
import math
import sys
import argparse
import os
import shutil
import collections
import subprocess

if os.path.islink(__file__):
    sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import config
import help

try:
    del FILE_CONFIG
except:
    pass

try:
    del CONFIG
except:
    pass

DEFAULT_POSTMAP = 'postmap'
CONFIG_FILE = 'config.yaml'
CONFIG = None
FILE_CONFIG = None


def get_config_path():
    if not os.path.isabs(CONFIG_FILE):
        path = os.path.dirname(os.path.realpath(__file__))
        return os.path.join(path, CONFIG_FILE)
    return CONFIG_FILE


def load_config(config_file=None):
    global CONFIG, CONFIG_FILE
    if CONFIG and config_file is not None and CONFIG.filename != config_file:
        raise RuntimeError('Config already loaded with config: %s. You tried to load %s.' %
                           (CONFIG.filename, config_file))
    if CONFIG is None:
        if config_file is None:
            config_file = get_config_path()
        CONFIG = config.Config(filename=config_file)
    return CONFIG


def load_file_config(config_file=None):
    global FILE_CONFIG, CONFIG_FILE, CONFIG
    CONFIG = load_config(config_file)
    if FILE_CONFIG is None:
        FILE_CONFIG = config.FileConfig(CONFIG)
    return FILE_CONFIG


class ParserError(Exception):
    pass


class PostfixTableParser(object):
    singleton_instance = None

    lines = [
        ('ENTRY', r'^(?P<K>[^#\s]\S+)(?P<MULTI>([ \t]*\n+)*)[ \t]+(?P<V>\S+)[ \t]*$'),
        ('DELETED', r'^[ \t]*#--[ \t]+(?P<DK>\S+)[ \t]+(?P<DV>\S+)[ \t]*$'),
        ('SYS_COMMENT', r'^[ \t]*#==([^\n]*)$'),
        ('COMMENT', r'^[ \t]*#(?P<C>.*)[^\n]*$'),
        ('EMPTY', r'^[ \t]*$'),
        ('ERROR', r'^.+$')
    ]
    line_expr = '|'.join("(?P<%s>%s)" % token for token in lines)
    line_re = re.compile(line_expr, re.MULTILINE)

    def __new__(cls, *args, **kwargs):
        if PostfixTableParser.singleton_instance is None:
            PostfixTableParser.singleton_instance = super().__new__(cls, *args, **kwargs)
        return cls.singleton_instance

    def parse(self,  data, table=None):
        if table is None:
            table = {}
        comment = []
        line = 0
        for match in self.line_re.finditer(data):
            line += 1
            kind = match.lastgroup
            values = match.groupdict()
            if kind == 'ENTRY':
                key = values['K']
                value = values['V']
                multiline = values.get('MULTI')
                if multiline is not None:
                    line += multiline.count('\n')
                if table:
                    table[key] = TableEntry(value, comment.copy(), line)
                else:
                    table[key] = TableEntry(value, [], line)
                comment = []
            elif kind == 'DELETED':
                key = values['DK']
                value = values['DV']
                if table:
                    table[key] = TableEntry(value, comment.copy(), line, True)
            elif kind == 'COMMENT':
                comment.append(values['C'].strip())
            elif kind == 'EMPTY':
                if not table:
                    table['#'] = TableEntry(None, comment.copy(), 0)
                    comment = []
            elif kind == 'SYS_COMMENT':
                pass
            elif kind == 'ERROR':
                raise ParserError("Syntax error in line '%s'" % (match.group()))
            else:
                raise ParserError("Parser error: Unkown kind '%s' in match '%s'" % (kind, match.group()))
        if comment:
            table[None] = TableEntry(None, comment, line)
        return table


class PFTableSerializer(object):
    @staticmethod
    def _sort_by_line_no(data):
        s = [{'key': k, 'entry': v} for k, v in sorted(data.items(), key=lambda t: t[1].line_no)]
        return s

    @staticmethod
    def serialize(data, original_order=False, print_system_comments=True):
        out = []
        comments = data.get('#', TableEntry()).comment
        for c in comments:
            out.append('# ' + c)
        if comments:
            out.append('')
        if not original_order:
            entries = PFTableSerializer._sort_by_line_no(data)
            entries.sort(key=lambda v: v['entry'].value if v['entry'].value else '')
        else:
            entries = PFTableSerializer._sort_by_line_no(data)
        max_len = 0
        for e in entries:
            key = '#-- ' + e['key'] if e['entry'].deleted else e['key']
            max_len = max(len(key), max_len)
        min_spaces = round(8 + (1-(max_len/8 - math.floor(max_len/8))) * 8)
        old_entry = ''
        for e in entries:
            entry = e['entry']
            key = '#-- ' + e['key'] if e['entry'].deleted else e['key']
            if key is not None and key != '#':
                if print_system_comments and not original_order and old_entry != entry.value:
                    old_entry = entry.value
                    if len(out) > 0 and out[-1]:
                        out.append('')
                    out.append("#== Entries for value '%s'" % old_entry)

                spaces = min_spaces + max_len - len(key)
                for comment in entry.comment:
                    out.append('# ' + comment)
                if entry.value is not None:
                    out.append((key + ' ' * spaces + entry.value))
        comments = data.get(None, TableEntry()).comment
        for c in comments:
            out.append('# ' + c)
        out.append('')
        return '\n'.join(out)


class FactoryError(Exception):
    pass


class ConfigError(Exception):
    pass


class Table(collections.abc.MutableMapping):
    parser = None
    files_dict_getter = None
    serializer = None
    table_singleton = True

    def __new__(cls, *args, **kwargs):
        if cls.table_singleton:
            f_path = args[0]
            attr_name = '_instances'
            if not hasattr(cls, attr_name):
                setattr(cls, attr_name, {})
            obj = cls._instances.get(f_path)
            if not obj:
                obj = super().__new__(cls)
                cls._instances[f_path] = obj
            return obj
        return super().__new__(cls)

    def __init__(self, file):
        self.file = file
        super().__init__()

    def __getitem__(self, item):
        return self._mapping[item]

    def __setitem__(self, key, value):
        self._mapping[key] = value

    def __delitem__(self, key):
        del self._mapping[key]

    def __iter__(self):
        return iter(self._mapping)

    def __len__(self):
        return len(self._mapping)

    def __getattr__(self, item):
        if item == '_mapping':
            self._initialize()
            return self._mapping
        raise AttributeError()

    def _initialize(self):
        self._parse_file(self.file)

    def _parse_file(self, filename):
        self._mapping = {}
        f_path = self.__class__.files_dict_getter().get(filename)
        if f_path is None:
            raise FactoryError("No Configuration entry for file %s" % filename)
        with open(f_path, 'r') as file:
            try:
                self.parser().parse(file.read(), self._mapping)
            except ParserError as e:
                raise FactoryError("Error while parsing %s under %s" % (filename, f_path)) from e

    def serialize(self, original_order=False, print_system_comments=True):
        return self.serializer.serialize(self, original_order=original_order,
                                         print_system_comments=print_system_comments)


class PostfixTable(Table):
    parser = PostfixTableParser
    files_dict_getter = load_file_config
    serializer = PFTableSerializer
    table_singleton = True

    def del_entry(self, key, comment_out=False):
        if key in self:
            if comment_out:
                self[key].deleted = True
            else:
                del self[key]


class TableEntry(object):
    def __init__(self, value=None, comment=None, line_no=0, deleted=False):
        if comment is None:
            comment = []
        self.value = value
        self.comment = comment
        self.line_no = line_no
        self.deleted = deleted

    def __eq__(self, other):
        is_class = isinstance(other, TableEntry)
        return is_class and self.value == other.value and self.comment == other.comment \
               and self.line_no == other.line_no and self.deleted == other.deleted

    def __repr__(self):
        return "Value: '%s', Comment: '%s', Line No.: '%s', Deleted: '%s'" % \
               (self.value, self.comment, self.line_no, self.deleted)

    def get_value(self):
        return '# ' + self.value if self.deleted else self.value


class DovecotPasswordFile(dict):
    pass


class Alias(object):
    def __init__(self, alias, sender, inbox):
        self.alias = alias
        self.sender = sender
        self.inbox = inbox


class PFAliasConfig(object):
    _virtual_alias = PostfixTable('virtual-alias')
    _sender_login_maps = PostfixTable('sender-login-maps')
    _users = PostfixTable('virtual-mailbox-users')

    def add_alias(self, alias, user, comment='', virtual_alias=True, sender_login_maps=True):
        if alias in self._virtual_alias and virtual_alias:
            raise ConfigError("An alias for %s already exists in 'virtual-alias'." % alias)
        if alias in self._sender_login_maps and sender_login_maps:
            raise ConfigError("An alias for %s already exists in 'sender-login-maps'." % alias)
        if user not in self._users:
            raise ConfigError("User '%s' does not exist." % user)
        if self._users[user].deleted:
            raise ConfigError("User '%s' does not exist." % user)

        if comment:
            if isinstance(comment, str):
                comment = comment.split('\n')

        if virtual_alias:
            self._virtual_alias[alias] = TableEntry(user, comment, sys.maxsize)
        if sender_login_maps:
            self._sender_login_maps[alias] = TableEntry(user, comment, sys.maxsize)

    def delete_alias(self, alias, comment_out=False, virtual_alias=True, sender_login_maps=True):
        if virtual_alias:
            self._virtual_alias.del_entry(alias, comment_out)
        if sender_login_maps:
            self._sender_login_maps.del_entry(alias, comment_out)

    def get_alias(self, alias):
        alias_data = self._virtual_alias.get(alias, None)
        sender_data = self._sender_login_maps.get(alias, None)
        data = Alias(alias, alias_data, sender_data)
        return data

    def get_alias_list(self, sort_by_inbox=False, sort_by_sender=False):
        aliases = []
        for alias in self._virtual_alias:
            aliases.append(self.get_alias(alias))
        for alias in self._sender_login_maps:
            if alias not in self._virtual_alias:
                aliases.append(self.get_alias(alias))

        if sort_by_sender:
            aliases.sort(key=lambda a: a.sender.value if a.sender and a.sender.value else '')

        if sort_by_inbox:
            aliases.sort(key=lambda a: a.inbox.value if a.inbox and a.inbox.value else '')

        return aliases

    def del_virtual_alias_user(self, user, comment_out=False):
        aliases = []
        for a, v in self._virtual_alias.items():
            if v.value == user:
                aliases.append(a)
        for a in aliases:
            self._virtual_alias.del_entry(a, comment_out)

    def del_sender_login_maps_user(self, user, comment_out=False):
        aliases = []
        for a, v in self._sender_login_maps.items():
            if v.value == user:
                aliases.append(a)
        for a in aliases:
            self._sender_login_maps.del_entry(a, comment_out)

    def serialize(self, virtual_alias=True, sender_login_maps=True):
        out = ''
        if virtual_alias:
            out += self._virtual_alias.serialize()
        if sender_login_maps:
            out += self._sender_login_maps.serialize()
        return out


class PFUserConfig(object):
    pf_files = ('virtual-mailbox-users',)


class App(object):
    alias_config = PFAliasConfig

    def __getattr__(self, item):
        if item == '_alias_config':
            self._alias_config = self.alias_config()
            return self._alias_config
        raise AttributeError()

    def list_aliases(self, args):
        if hasattr(args, 'as_saved') and args.as_saved:
            return self._alias_config.serialize()

        out = []
        aliases = self._alias_config.get_alias_list(True, True)
        max_alias_len = 6
        max_inbox_len = 6
        max_sender_len = 7

        for alias in aliases:
            max_alias_len = max(len(alias.alias), max_alias_len)
            if alias.inbox and alias.inbox.value:
                max_inbox_len = max(len(alias.inbox.get_value()), max_inbox_len)
            if alias.sender and alias.sender.value:
                max_sender_len = max(len(alias.sender.get_value()), max_sender_len)

        min_alias_spaces = round(4 + (1 - (max_alias_len/4 - math.floor(max_alias_len/4))) * 4)
        min_inbox_spaces = round(4 + (1 - (max_inbox_len/4 - math.floor(max_inbox_len/4))) * 4)
        alias_spaces = min_alias_spaces + max_alias_len - 6
        inbox_spaces = min_inbox_spaces + max_inbox_len - 6
        out.append('Alias:' + ' ' * alias_spaces + 'Inbox:' + ' ' * inbox_spaces + 'Sender:')
        out.append('-' * (max_inbox_len + min_inbox_spaces + max_alias_len + min_alias_spaces + max_sender_len))

        for alias in aliases:
            if alias.alias != '#' and alias.alias is not None:
                alias_spaces = min_alias_spaces + max_alias_len - len(alias.alias)
                if alias.inbox and alias.inbox.value:
                    inbox = alias.inbox.get_value()
                    inbox_spaces = min_inbox_spaces + max_inbox_len - len(inbox)
                else:
                    inbox = ''
                    inbox_spaces = min_inbox_spaces + max_inbox_len
                if alias.sender and alias.sender.value:
                    sender = alias.sender.get_value()
                else:
                    sender = ''
                out.append(alias.alias + ' ' * alias_spaces + inbox + ' ' * inbox_spaces + sender)
        return "\n".join(out)

    @staticmethod
    def _getpostmap():
        c = load_config()
        postmap = c.get('postmap')
        if postmap is None:
            postmap = DEFAULT_POSTMAP
        return postmap

    @staticmethod
    def _which(cmd):
        path = shutil.which(cmd)
        if path is None:
            raise RuntimeError("Command %s couldn't be found. No changes have been written." % cmd)

    def _exec(self, args, stdin=None, stdout=None, stderr=None):
        with subprocess.Popen(args, stdin=stdin, stdout=stdout, stderr=stderr) as p:
            p.communicate()
            print("Executed: %s" % " ".join(args))
            return p

    def _exec_postmap(self, file):
        args = [self._getpostmap(), file]
        p = self._exec(args, stdout=subprocess.PIPE)
        if p.returncode != 0:
            raise RuntimeError("Return code from %s was %s. Unable to generate %s.db." %
                               (self._getpostmap(), p.returncode, file))

    def _save_alias_tables(self, args):
        self._which(self._getpostmap())
        virtual_alias = self._alias_config.serialize(True, False)
        sender_login_maps = self._alias_config.serialize(False, True)
        if not args.save:
            return self.list_aliases(args)
        else:
            fc = load_file_config()
            with open(fc['virtual-alias'], 'w') as file:
                file.write(virtual_alias)
            with open(fc['sender-login-maps'], 'w') as file:
                file.write(sender_login_maps)
            self._exec_postmap(fc['virtual-alias'])
            self._exec_postmap(fc['sender-login-maps'])
            return 'Successfully saved.'

    def add_alias(self, args):
        if hasattr(args, 'comment'):
            comment = args.comment
        else:
            comment = ''
        self._alias_config.add_alias(args.alias, args.user, comment)
        return self._save_alias_tables(args)

    def delete_alias(self, args):
        self._alias_config.delete_alias(args.alias, args.comment_out)
        return self._save_alias_tables(args)

    def delete_alias_user(self, args):
        self._alias_config.del_sender_login_maps_user(args.user)
        self._alias_config.del_virtual_alias_user(args.user)
        return self._save_alias_tables(args)


def init_args_parser(parser, obj):
    parser.set_defaults(**obj.get('defaults', {}))
    for a in obj.get('arguments', []):
        a = a.copy()
        name = a['name']
        del a['name']
        parser.add_argument(name, **a)
    for a in obj.get('options', []):
        a = a.copy()
        name = a['name']
        del a['name']
        parser.add_argument(name, **a)

    args_parser_from_list(parser, obj.get('commands', []), obj.get('commands-title', 'commands'),
                          obj.get('commands-help', ''))


def args_parser_from_list(parser, objects, kind, helptext=''):
    if objects:
        sub = parser.add_subparsers(title=kind, required=True, dest=kind, help=helptext)
        for o in objects:
            p = sub.add_parser(o['name'], help=o['help'])
            init_args_parser(p, o)


def create_args_parser(cls):
    parser = argparse.ArgumentParser()
    init_args_parser(parser, cls.main)
    return parser


def parse_args(cls, argv):
    parser = create_args_parser(cls)
    return parser.parse_args(argv[1:])


if __name__ == "__main__":
    args = parse_args(help.Help, sys.argv)
    cfg = args.config_file if args.config_file else CONFIG
    cf = load_file_config(cfg)
    app = App()
    action = getattr(app, args.action)
    try:
        print(action(args))
    except Exception as e:
        print(e.with_traceback(), file=sys.stderr)

