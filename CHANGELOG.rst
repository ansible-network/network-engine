==============================
Ansible Network network-engine
==============================

.. _Ansible Network network-engine_v2.5.3:

v2.5.3
======

.. _Ansible Network network-engine_v2.5.3_Minor Changes:

Minor Changes
-------------

- Templating the regex sent to the parser to allow us to use ansible variables in the regex string `network-engine#97 <https://github.com/ansible-network/network-engine/pull/97>`_.


.. _Ansible Network network-engine_v2.5.3_Removed Features (previously deprecated):

Removed Features (previously deprecated)
----------------------------------------

- Move yang2spec lookup to feature branch, till the right location for this plugin is identified `network-engine#100 <https://github.com/ansible-network/network-engine/pull/100>`_.


.. _Ansible Network network-engine_v2.5.2:

v2.5.2
======

.. _Ansible Network network-engine_v2.5.2_Minor Changes:

Minor Changes
-------------

- Add new directives extend `network-engine#91 <https://github.com/ansible-network/network-engine/pull/91>`_.

- Adds conditional support to nested template objects `network-engine#55 <https://github.com/ansible-network/network-engine/pull/55>`_.


.. _Ansible Network network-engine_v2.5.2_New Lookup Plugins:

New Lookup Plugins
------------------

- New lookup plugin ``json_template``

- New lookup plugin ``network_template``

- New lookup plugin ``yang2spec``

- New lookup plugin ``netcfg_diff``


.. _Ansible Network network-engine_v2.5.2_New Filter Plugins:

New Filter Plugins
------------------

- New filter plugin ``interface_range``

- New filter plugin ``interface_split``

- New filter plugin ``vlan_compress``

- New filter plugin ``vlan_expand``


.. _Ansible Network network-engine_v2.5.2_New Tasks:

New Tasks
---------

- New task ``cli``


.. _Ansible Network network-engine_v2.5.2_Bugfixes:

Bugfixes
--------

- Fix AnsibleFilterError, deprecations, and unused imports `network-engine#82 <https://github.com/ansible-network/network-engine/pull/82>`_.


.. _Ansible Network network-engine_v2.5.1:

v2.5.1
======

.. _Ansible Network network-engine_v2.5.1_Deprecated Features:

Deprecated Features
-------------------

- Module ``text_parser`` renamed to ``command_parser``; original name deprecated; legacy use supported; will be removed in 2.6.0.

- Module ``textfsm`` renamed to ``textfsm_parser``; original name deprecated; legacy use supported; will be removed in 2.6.0.


.. _Ansible Network network-engine_v2.5.1_New Modules:

New Modules
-----------

- New module ``command_parser`` (renamed from ``text_parser``)

- New module ``textfsm_parser`` (renamed from ``textfsm``)


.. _Ansible Network network-engine_v2.5.1_Bugfixes:

Bugfixes
--------

- Fix ``command_parser`` Absolute path with tilde in src should work `network-engine#58 <https://github.com/ansible-network/network-engine/pull/58>`_

- Fix content mush only accepts string type `network-engine#72 <https://github.com/ansible-network/network-engine/pull/72>`_

- Fix StringIO to work with Python3 in addition to Python2 `network-engine#53 <https://github.com/ansible-network/network-engine/pull/53>`_


.. _Ansible Network network-engine_v2.5.1_Documentation Updates:

Documentation Updates
---------------------

- User Guide `docs/user_guide <https://github.com/ansible-network/network-engine/tree/devel/docs/user_guide>`_.


.. _Ansible Network network-engine_v2.5.0:

v2.5.0
======

.. _Ansible Network network-engine_v2.5.0_Major Changes:

Major Changes
-------------

- Initial release of the ``network-engine`` Ansible role.

- This role provides the foundation for building network roles by providing modules and plugins that are common to all Ansible Network roles. All of the artifacts in this role can be used independent of the platform that is being managed.


.. _Ansible Network network-engine_v2.5.0_New Modules:

New Modules
-----------

- NEW ``text_parser`` Parses ASCII text into JSON facts using text_parser engine and YAML-formatted input. Provides a rules-based text parser that is closely modeled after the Ansible playbook language. This parser will iterate over the rules and parse the output of structured ASCII text into a JSON data structure that can be added to the inventory host facts.

- NEW ``textfsm`` Parses ASCII text into JSON facts using textfsm engine and Google TextFSM-formatted input. Provides textfsm rules-based templates to parse data from text. The template acting as parser will iterate of the rules and parse the output of structured ASCII text into a JSON data structure that can be added to the inventory host facts.

