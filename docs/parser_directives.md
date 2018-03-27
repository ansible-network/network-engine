CLI Parser Directives
=====================
The ```text_parser``` module is a module that can be used to parse the results of
text strings into Ansible facts.  The primary motivation for developing the
```text_parser``` module is to convert structured ASCII text output (such as
those returned from network devices) into  JSON data structures sutable to be 
used as host facts.

The parser file format is loosely based on the Ansible playbook directives
language.  It uses the Ansible directive language to ease the transition from
writing playbooks to writing parsers.  However, parsers developed using this 
module are not written directly into the playbook, but are a separate file
called from playbooks.  This is done for a variety of reasons but most notably
to keep separation from the parsing logical and playbook execution. 

The ```text_parser``` works based on a set of directives that perform actions
on structured data with the end result being a valid JSON structure that can be
returned to the Ansible facts system.

## Parser language 
The parser format uses YAML formatting, providing an ordered list of directives 
to be performed on the contents (provided by the module argument).  The overall 
general structure of a directive is as follows:

```
- name: some description name of the task to be performed
  directive:
    argument: value
      argument_option: value
    argument: value
  directive_option: value
  directive_option: value
```

The ```text_parser``` currently supports the following top-level directives:

* pattern_match
* pattern_group
* json_template
* export_facts

In addition to the directives, the following common directive options are
currently supported.

* name
* block
* loop
* loop_control
    * loop_var
* when
* register
* export
* export_as

Any of the directive options are accepted but in some cases, the option may
provide no operation.  For instance, when using the ```export_facts```
directive, the options ```register```, ```export``` and ```export_as``` are all
ignored.  The module should provide warnings when an option is ignored.

The following sections provide more details about how to use the parser
directives to parse text into JSON structure.

## Directive Options
This section provides details on the various options that are available to be
configured on any directive.

### name
All entries in the parser file many contain a ```name``` directive.  The
```name``` directive can be used to provide an arbitrary description as to the
purpose of the parser items.  The use of ```name``` is optional for all 
directives.


The default value for ```name``` is ```null```

### register
The ```register``` directive option can be used same as would be used in an
Ansible playbook.  It will register the results of the directive operation into
the named variable such that it can be retrieved later.  

However, be sure to make note that registered variables are not available
outside of the parser context.  Any values registered are only availalbe within
the scope of the parser activities.  If you want to provide values back to the
playbook, you will have to define the [export](#export) option.


The default value for ```register``` is ```null```

### export
This option will allow any value to be exported back the calling task as an
Ansible fact.  The ```export``` option accepts a boolean value that defines if
the registered fact should be exported to the calling task in the playbook (or
role) scope.  To export the value, simply set ```export``` to True.  

Note this option requires the ```register``` value to be set in some cases and will
produce a warning message if the ```register``` option is not provided.

The default value for ```export``` is ```False```

### export_as
TBD


### loop
Sometimes it is necessary to loop over a directive in order to process values.
Using the ```loop``` option, the parser will iterate over the directive and
provide each of the values provided by the loop contents to the directive for
processing.  

Access to the individual items is the same as it would be for Ansible
playbooks.  When iterating over a list of items, you can access the individual
item using the ```{{ item }}``` variable.  When looping over a hash, you can
access ```{{ item.key }}``` and ```{{ item.value }}```.

### loop_control
TBD

### when
The ```when``` option allows for a conditional to be placed on the directive to
decided if it is executed or not.  The ```when``` option operates the same as
it would in an Ansible playbook.

For example, let's assume we only want to match perform the match statement
when the value of ```ansible_network_os``` is set to ``ios```.  We would apply
the ```when``` conditional as such:

```
- name: conditionally matched var
  pattern_match:
    regex: "hostname (.+)"
  when: ansible_network_os == 'ios'
```

## Directives
The directives perform actions on the contents using regular expressions to
extract various values.  Each directive provides some additional arguments that
can be used to perform its operation.  

### pattern_match
The ```pattern_match``` directive is used to extract one or more values from
the structured ASCII text based on regular expressions.

The following arguments are supported for this directive:

* regex
* contents
* match_all
* match_greedy


### pattern_group
The ```pattern_group``` directive can be used to group multiple
```pattern_match``` results together.  


The following arguments are supported for this directive:

### json_template
The ```json_template``` directive will create a JSON data structure based on a
template.  This directive will allow you to template out a multi-level JSON
blob.  

The following arguments are supported for this directive:

* template


### set_vars


### export_facts
The ```export_facts``` directive takes an arbitrary set of key / value pairs
and exposes (returns) them back to the playbook global namespace.  Any key /
value pairs that are provided in this directive become available on the host.


