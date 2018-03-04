#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2018, Ansible by Red Hat, inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'network'}

DOCUMENTATION = """
---
module: cli_get
author: Ansible Network Team
short_description: Runs the specific command and returns the output
description:
  - The command specified in C(command) will be executed on the remote
    device and its output will be returned to the module.  This module
    requires that the device is supported using the C(network_cli)
    connection plugin and has a valid C(cliconf) plugin to work correctly.
version_added: "2.5"
options:
  command:
    description:
      - The command to be executed on the remote node.  The value for this
        argument will be passed unchanged to the network device and the
        the ouput returned.
    required: yes
    default: null
"""

EXAMPLES = """
- name: return show version
  cli_get:
    command: show version
"""

RETURN = """
output:
  description: returns the output from the command
  returned: always
json:
  description: the output converted from json to a hash
  returned: always
"""
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


def main():
    """main entry point for module execution
    """
    argument_spec = dict(
        command=dict(required=True),
    )

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True)

    command = module.params['command']

    connection = Connection(module._socket_path)

    output = connection.get(command)

    try:
        json_out = module.from_json(output)
    except:
        json_out = None

    result = {
        'changed': False,
        'stdout': output,
        'json': json_out
    }

    module.exit_json(**result)


if __name__ == '__main__':
    main()
