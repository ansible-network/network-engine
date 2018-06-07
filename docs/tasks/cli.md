# Task cli
The ```cli``` task provides an implementation for running CLI commands on
network devices that is platform agnostic. The ```cli``` task accepts a
command and will attempt to execute that command on the remote device returning
the command ouput.

If the ```parser``` argument is provided, the output from the command will be
passed through the parser and returned as JSON facts using the ```engine```
argument.


## Requirements
The following is the list of requirements for using the this task:

* Ansible 2.5 or later
* Connection ```network_cli```
* ansible_network_os

## Arguments
The following are the list of required and optional arguments supported by this
task.

### command
This argument specifies the command to be executed on the remote device. The
```command``` argument is a required value.

### parser
This argument specifies the location of the parser to pass the output from the command to
in order to generate JSON data. The ```parser``` argument is an optional value, but required
when ```engine``` is used.

### engine
The ```engine``` argument is used to define which parsing engine to use when parsing the output
of the CLI commands. This argument uses the file specified to ```parser``` for parsing output to
JSON facts. This argument requires ```parser``` argument to be specified.

This action currently supports two different parsers:

* ```command_parser```
* ```textfsm_parser```

The default value is ```command_parser```.
