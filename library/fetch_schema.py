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
module: fetch_schema
short_description: Fetch a given schema and its dependant schemas.
description:
    - Fetch given schema and its dependant schems from device using netconf rpc.
version_added: "2.7"
options:
  schemas:
    description:
      - List of schemas to be fecthed from device.
    required: true
  destination:
    description:
      - Absolute path of destination folder where schemas will be stored.
    default:
      - The schemas will be written to the C(yang_schemas) folder in the
        playbook root directory or role root directory, if playbook is
        part of an ansible role. If the directory does not exist, it is
        created.
author:
  - Deepak Agrawal
'''

EXAMPLES = '''
- fetch_schema:
    schemas:
       - openconfig-interface
       - openconfig-bgp
    desctination: ~/.ansible/tmp/yang
'''
