# text_paser

The module `text_parser` provides rule based text parser that is closely modeled
after the Ansible playbook language. This parser will iterate of the rules and
parse the output of structured ASCII text into a JSON data structure that can be
added to the inventory host facts.

## Playbook

```yaml

---
# The following task runs on localhost.

- hosts: localhost

  tasks:
  - name: Genereta interface facts as JSON
    text_parser:
      file: "parsers/ios/show_interfaces.yaml"
      content: "{{ lookup('file', 'output/ios/show_interfaces.txt') }}"

  - name: Generate system facts as JSON
    text_parser:
      file: "parsers/ios/show_version.yaml"
      content: "{{ lookup('file', 'output/ios/show_version.txt') }}"


# The following task runs against network device

- hosts: ios

  tasks:
  - name: Collect interface information from device
    ios_command:
      commands: "show interfaces"
    register: ios_interface_output

  - name: Generate interface facts as JSON
    text_parser:
      file: "parsers/ios/show_interfaces.yaml"
      content: ios_interface_output['stdout'][0]

```

## Parser
The `file` parameter for `text_parser` contains rules to parse text.
The rules in parser file uses directives written closely to Ansible language.

Directives documentation is available [Here](https://github.com/ansible-network/network-engine/blob/devel/docs/directives/parser_directives.md).

The following describes how a parser file looks like:

`parser/ios/show_interfaces.yaml`
```yaml

---
- name: parser meta data
  parser_metadata:
    version: 1.0
    command: show interface
    network_os: ios

- name: match sections
  pattern_match:
    regex: "^(\\S+) is up,"
    match_all: yes
    match_greedy: yes
  register: section

- name: match interface values
  pattern_group:
    - name: match name
      pattern_match:
        regex: "^(\\S+)"
        content: "{{ item }}"
      register: name

    - name: match hardware
      pattern_match:
        regex: "Hardware is (\\S+),"
        content: "{{ item }}"
      register: type

    - name: match mtu
      pattern_match:
        regex: "MTU (\\d+)"
        content: "{{ item }}"
      register: mtu

    - name: match description
      pattern_match:
        regex: "Description: (.*)"
        content: "{{ item }}"
      register: description
  loop: "{{ section }}"
  register: interfaces

- name: generate json data structure
  json_template:
    template:
      - key: "{{ item.name.matches.0 }}"
        object:
        - key: config
          object:
            - key: name
              value: "{{ item.name.matches.0 }}"
            - key: type
              value: "{{ item.type.matches.0 }}"
            - key: mtu
              value: "{{ item.mtu.matches.0 }}"
            - key: description
              value: "{{ item.description.matches.0 }}"
  loop: "{{ interfaces }}"
  export: yes
  register: interface_facts

```

`parser/ios/show_version.yaml`

```yaml

---
- name: parser meta data
  parser_metadata:
    version: 1.0
    command: show version
    network_os: ios

- name: match version
  pattern_match:
    regex: "Version (\\S+),"
  register: version

- name: match model
  pattern_match:
    regex: "^Cisco (.+) \\(revision"
  register: model

- name: match image
  pattern_match:
    regex: "^System image file is (\\S+)"
  register: image

- name: match uptime
  pattern_match:
    regex: "uptime is (.+)"
  register: uptime

- name: match total memory
  pattern_match:
    regex: "with (\\S+)/(\\w*) bytes of memory"
  register: total_mem

- name: match free memory
  pattern_match:
    regex: "with \\w*/(\\S+) bytes of memory"
  register: free_mem

- name: export system facts to playbook
  set_vars:
    model: "{{ model.matches.0 }}"
    image_file: "{{ image.matches.0 }}"
    uptime: "{{ uptime.matches.0 }}"
    version: "{{ version.matches.0 }}"
    memory:
      total: "{{ total_mem.matches.0 }}"
      free: "{{ free_mem.matches.0 }}"
  export: yes
  register: system_facts

```

## Content

The `content` paramter for `text_parser` should have the ASCII text output of commands run on
network devices.
