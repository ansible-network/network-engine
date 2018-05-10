# textfsm

The module [textfsm](https://github.com/ansible-network/network-engine/blob/devel/library/textfsm.py)
provides [textfsm](https://github.com/google/textfsm/wiki/TextFSM) rule based templates to parse data
from text and returns JSON facts as `ansible_facts`. The document describes how to use textfsm module.

## Playbook

```yaml

---
# The following task runs on Ansible controller localhost.

- hosts: localhost

  tasks:
  - name: Generate interface facts as JSON
    textfsm:
      file: "parsers/ios/show_interfaces"
      content: "{{ lookup('file', 'output/ios/show_interfaces.txt') }}"
      name: interface_facts


# The following task runs against network device

- hosts: ios

  tasks:
  - name: Collect interface information from device
    ios_command:
      commands: "show interfaces"
    register: ios_interface_output

  - name: Generate interface facts as JSON
    textfsm:
      file: "parsers/ios/show_interfaces"
      content: ios_interface_output['stdout'][0]
      name: interface_facts

```

## Parser

The `file` parameter for `textfsm` contains the standard textfsm rules.

The following describes how a parser file looks like:

`parsers/ios/show_interfaces`
```

Value Required name (\S+)
Value type ([\w ]+)
Value description (.*)
Value mtu (\d+)

Start
  ^${name} is up
  ^\s+Hardware is ${type} -> Continue
  ^\s+Description: ${description}
  ^\s+MTU ${mtu} bytes, -> Record

```

## Content

The `content` paramter for `textfsm` should have the ASCII text output of commands run on
network devices.
