# Textfsm

The module `textfsm` provides [textfsm](https://github.com/google/textfsm/wiki/TextFSM) rule
based templates to parse data from text and returns JSON facts as `ansible_facts`.
The document describes how to use textfsm module.

## Playbook

```yaml

---
# The following task runs on localhost.

- hosts: localhost

  tasks:
  - name: Genereta interface facts as JSON
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
      content: ios_interface_output
      name: interface_facts

```

## textfsm template
The `file` parameter for textfsm is the standard template that is used for textfsm

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

## textfsm content

The `content` paramter for textfsm should have the ASCII text output of commands run on
network devices.
