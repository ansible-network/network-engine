CLI Parser Directives
=====================
The ```text_parser``` module is a module that can be used to parse the results of
text strings into Ansible facts.  The primary motivation for developing the
```text_parser``` module is to convert structured ASCII text output (such as
those returned from network devices) into structured JSON data structures
sutable to be used as host facts.

The parser file format is loosely based on the Ansible playbook directives
language.  It uses the Ansible directive language to ease the transition from
writing playbooks to writing parsers.  Below is the set of supported directives
the ```text_parser``` module recognizes along with a description of the
directives basic functionality.

## Parser language 
The parse supports an Ansible-like playbook parser language that is loosely 
designed after the current Ansible language.  It implements a set of directives
that are designed to perform specific actions.  

The parser format uses YAML formatting, providing a list sequential list of
directives to be performed on the contents (provided by the module argument).
The overall general structure of a directive is as follows:

```
- name: some description name of the task to be performed
  directive:
    key: value
    key: value
  directive_option: value
  directive_option: value
```

The ```text_parser``` currently supports the following directives:

* pattern_match
* pattern_group
* json_template
* export_facts

In addition to the directives, the following common directive options are
currently supported.

* name
* block
* loop
* when
* register

The following sections provide more details about how to use the parser
directives to parse text into JSON structure.

## Directive Options
This section provides details on the various options that are available to be
configured on any directive.

### name
All entries in the parser file many contain a ```name``` directive.  The
```name``` directive can be used to provide an arbitrary description as to the
purpose of the parser items.

The use of ```name``` is optional for all directives.

### register
The ```register``` directive option can be used same as would be used in an
Ansible playbook.  It will register the results of the directive operation into
the named variable such that it can be retrieved later.  

However, be sure to make note that registered variables are not available
outside of the parser context.  Any values registered are only availalbe within
the scope of the parser activities.  If you want to provide values back to the
playbook, use the [export-facts](#export_facts) directive.

### export
This option will short circuit the export of facts to the playbook.  The
```export``` option accepts a boolean value and when configured to True, it
will cause the registered value to be exported to the playbook.  When setting
```export``` to True, no additional call to [export-facts](#export_facts) is
required.  

The default value for ```export``` is False.

### loop
Sometimes it is necessary to loop over a directive in order to process values.
Using the ```loop``` option, the parser will iterate over the directive and
provide each of the values provided by the loop contents to the directive for
processing.  

Access to the individual items is the same as it would be for Ansible
playbooks.  When iterating over a list of items, you can access the individual
item using the ```{{ item }}``` variable.  When looping over a hash, you can
access ```{{ item.key }}``` and ```{{ item.value }}```.

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

### block
The use of ```block``` allows for grouping items together to perform a common
set of matches.  Typically this directive will be used when you need to iterate
over a block of text to find multiple matches.  

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


### export_facts
The ```export_facts``` directive takes an arbitrary set of key / value pairs
and exposes (returns) them back to the playbook global namespace.  Any key /
value pairs that are provided in this directive become available on the host.

