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
module: cli
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
  parser:
    description:
      - The parser file to pass the output from the command through to
        generate Ansible facts.  If this argument is specified, the output
        from the command will be parsed based on the rules in the
        specified parser.
    required: no
    default: null
  engine:
    description:
      - Defines the engine to use when parsing the output.  This arugment
        accepts one of two valid values, c(text_parser) or c(textfsm).  The
        default is C(text_parser)
    required: no
    default: text_parser
    choices:
      - text_parser
      - textfsm
"""

EXAMPLES = """
- name: return show version
  cli:
    command: show version

- name: return parsed command output
  cli:
    command: show version
    parser: parsers/show_version.yaml
"""

RETURN = """
stdout:
  description: returns the output from the command
  returned: always
json:
  description: the output converted from json to a hash
  returned: always
"""
