# Copyright (c) 2018 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)


from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import re

from ansible.module_utils.six import string_types
from ansible.errors import AnsibleFilterError


def interface_split(interface, key=None):
    match = re.match(r'([A-Za-z\-]*)(.+)', interface)
    if not match:
        raise FilterError('unable to parse interface %s' % interface)
    obj = {'name': match.group(1), 'index': match.group(2)}
    if key:
        return obj[key]
    else:
        return obj


def interface_range(interface):
    if not isinstance(interface, string_types):
        raise AnsibleFilterError('value must be of type string, got %s' % type(interface))

    parts = interface.rpartition('/')
    if parts[1]:
        prefix = '%s/' % parts[0]
        index = parts[2]
    else:
        match = re.match(r'([A-Za-z]*)(.+)', interface)
        if not match:
            raise FilterError('unable to parse interface %s' % interface)
        prefix = match.group(1)
        index = match.group(2)

    indicies = list()

    for item in index.split(','):
        tokens = item.split('-')

        if len(tokens) == 1:
            indicies.append(tokens[0])

        elif len(tokens) == 2:
            start, end = tokens
            for i in range(int(start), int(end) + 1):
                indicies.append(i)
                i += 1

    return ['%s%s' % (prefix, index) for index in indicies]


class FilterModule(object):
    ''' Network interface filter '''

    def filters(self):
        return {
            'interface_split': interface_split,
            'interface_range': interface_range
        }
