class Help(object):
    save_option = {
        'name': '--save',
        'help': "Save file instead of printing to stdout.",
        'action': 'store_true'
    }
    comment_out_option = {
        'name': '--comment-out',
        'help': 'Marks the entry as comment.',
        'action': 'store_true',
    }
    comment_option = {
        'name': '--comment',
        'help': 'A comment to be added to the file(s)',
        'default': '',
    }
    objects = [
        {
            'name': 'alias',
            'help': 'Manipulates or lists aliases in the virtual-alias and sender-login-maps tables.',
            'commands-title': 'Commands',
            'commands-help': 'Action to execute',
            'commands': [
                {
                    'name': 'del',
                    'help': 'Deletes an existing email alias.',
                    'arguments': [
                        {
                            'name': 'alias',
                            'help': 'Alias to be deleted.'
                        }
                    ],
                    'options': [
                        save_option,
                        comment_out_option,
                    ],
                    'defaults': {'action': 'delete_alias'}
                },
                {
                    'name': 'deluser',
                    'help': 'Deletes all existing aliases for an user.',
                    'arguments': [
                        {
                            'name': 'user',
                            'help': 'User which aliases get deleted'
                        }
                    ],
                    'options': [
                        save_option,
                        comment_out_option,
                    ],
                    'defaults': {'action': 'delete_alias_user'}
                },
                {
                    'name': 'list',
                    'help': 'Lists existing email aliases.',
                    'options': [
                        {
                            'name': '--as-saved',
                            'help': 'Prints the files as written.',
                            'action': 'store_true',
                        },
                    ],
                    'defaults': {'action': 'list_aliases'}
                },
                {
                    'name': 'add',
                    'help': 'Adds a new email alias.',
                    'options': [
                        save_option,
                        comment_option,
                    ],
                    'arguments': [
                        {
                            'name': 'alias',
                            'help': 'The alias to be added.'
                        },
                        {
                            'name': 'user',
                            'help': 'An already existing email user'
                        }
                    ],
                    'defaults': {'action': 'add_alias'}
                },
            ]
        },
        {
            'name': 'user',
            'help': 'Manipulates or lists users in the virtual-mailbox-users and Dovecot users table.',
            'commands-title': 'Commands',
            'commands-help': 'Action to execute',
            'commands': [
                {
                    'name': 'add',
                    'help': 'Adds a new email user.',
                    'options': [
                        comment_option,
                    ],
                    'arguments': [
                        {
                            'name': 'user',
                            'help': 'Email user to be added.'
                        }
                    ]
                },
            ]
        },
        {
            'name': 'domain',
            'help': 'Manipulates or lists domains in the virtual-mailbox-domains table.',
            'commands-title': 'Commands',
            'commands-help': 'Action to execute',
            'commands': []
        },
    ]
    main = {
        'name': 'objects',
        'help': 'object to show or edit.',
        'commands-title': 'Objects',
        'commands-help': 'Object to edit',
        'commands': objects,
        'options': [
            {
                'name': '--config-file',
                'help': 'Use this config instead default.'
            }
        ]
    }


