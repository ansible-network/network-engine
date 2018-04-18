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
module: edit_config
short_description: Edit the configuration on the remote device
description:
  - This module will connect to the remote network device and edit the
    running configuration. This module also supports editing configuration
    in I(startup) or I(candidate) datastore based in the value of C(source) argument,
    provided the remote host supports it.
version_added: "2.5"
options:
  config:
    description:
      - The configuration string that should be applied on remote host
    required: True
  source:
    description:
      - Specifies the datastore in which the configuration should ne applied.
    required: false
    default: running
    choices:
      - running
      - candidate
      - startup
  backup:
    description:
      - This argument will cause the module to create a full backup of
        the current C(running-config) from the remote device before any
        changes are made.  The backup file is written to the C(backup)
        folder in the playbook root directory.  If the directory does not
        exist, it is created.
    required: false
    default: no
    choices: ['yes', 'no']
author:
  - Ansible Network Team
"""

EXAMPLES = """
- name: return the current device config
  edit_config:
    config: "hostname localhost\nip domain-name ansible.com"
    source: running
"""

RETURN = """
backup_path:
  description: The full path to the backup file
  returned: when backup is yes
  type: string
  sample: /playbooks/ansible/backup/config.2016-07-16@22:28:34
"""
import json

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection
from ansible.module_utils._text import to_text


def main():
    """main entry point for module execution
    """
    argument_spec = dict(
        source=dict(default='running', choices=['running', 'candidate', 'startup']),
        config=dict(required=True),

        # config operations
        backup=dict(type='bool', default=False),
    )

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True)

    source = module.params['source']
    config = module.params['config']

    conn = Connection(module._socket_path)
    capability = json.loads(conn.get_capabilities())
    result = {'changed': False}

    if module.params['backup']:
        output = conn.get_config(source=source, format=format)
        result['__backup__'] = to_text(output, errors='surrogate_then_replace').strip()

    conn.edit_config(config)

    if 'commit' in capability['rpc']:
        conn.commit()

    result['changed'] = True

    module.exit_json(**result)


if __name__ == '__main__':
    main()
