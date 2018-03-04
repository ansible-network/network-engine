#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2018 Red Hat
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'network'}


DOCUMENTATION = '''
---
module: text_parser
short_description: Parses text into JSON facts based on rules
description:
  - Provides a rules base text parser that is closely modeled after the Ansible
    playbook language.  This parser will iterate of the rules and parse the
    output of structured ASCII text into a JSON data structure that can be
    added to the inventory host facts.
version_added: "2.5"
options:
  dir:
    description:
      - The path to the directory that contains the parsers.  The module will
        load all parsers found in this directory and pass the contents through
        the them.  This argument is mutually exclusive with C(file).
    required: false
    default: null
  file:
    description:
      - The path to the parser to load from disk on the Ansible
        controller.  This can be either the absolute path or relative path.
        This argument is mutually exclusive with C(dir).
    required: false
    default: null
  contents:
    description:
      - The text contents to pass to the parser engine.  This argument provides
        the input to the text parser for generating the JSON data.
    required: true
author:
  - Ansible Network Team
'''

EXAMPLES = '''
- text_parser:
    parser: files/parsers/show_interface.yaml
    contents: "{{ lookup('file', 'output/show_interfaces.txt') }}"
'''
