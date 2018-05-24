#
#  Copyright 2018 Red Hat | Ansible
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

DOCUMENTATION = """
    lookup: yang2spec
    version_added: "2.5"
    short_description:  This plugin reads the content of given yang document and transforms it to a
                        rules spec and configuration schema.
    description:
      - This plugin parses yang document and transforms it into a spec which provides a set of rules
        This rules spec can be used to validate the input configuration to check  if it adheres
        with respective yang model. It also outputs the  configuration schema in json format and can
        be used as reference to build input json configuration.
    options:
      _terms:
        description: The path points to the location of the top level yang module which
        is to be transformed into to Ansible spec.
        required: True
      search_path:
        description:
          - The path is a colon (:) separated list of directories to search for imported yang modules
            in the yang file mentioned in C(path) option. If the value is not given it will search in
            the current directory.
        required: false
"""

EXAMPLES = """
- name: Get interface yang spec
  set_fact:
    interfaces_spec: "{{ lookup('yang2spec', 'openconfig/public/release/models/interfaces/openconfig-interfaces.yang',
                            search_path='openconfig/public/release/models:pyang/modules/') }}"
"""

RETURN = """
  _list:
    description:
      - It returns the rules spec and json configuration schema.
    type: complex
    contains:
      spec:
        description: The rules spec in json format generated from given yang document
        returned: success
        type: dict
        sample: |
          {
            "options": {
                "interfaces": {
                    "suboptions": {
                        "interface": {
                            "suboptions": {
                                "config": {
                                    "suboptions": {
                                        "description": {
                                            "type": "str"
                                        },
                                        "enabled": {
                                            "default": "true",
                                            "type": "boolean"
                                        },
                                        "loopback_mode": {
                                            "default": "false",
                                            "type": "boolean"
                                        },
                                        "mtu": {
                                            "restriction": {
                                                "int_size": 16,
                                                "max": 65535,
                                                "min": 0
                                            },
                                            "type": "int"
                                        },
                                        "name": {
                                            "type": "str"
                                        },
                                    }
                                },
                                "suboptions_elements": "dict",
                                "suboptions_type": "list"
                            }
                        }
                    }
                }
            }
          }
      config_schema:
        description: The json configuration schema generated from yang document
        returned: success
        type: dict
        sample: |
          {
            "interfaces": {
                "interface": {
                    "config": [
                        {
                            "description": null,
                            "enabled": true,
                            "loopback_mode": false,
                            "mtu": null,
                            "name": null,
                            "type": null
                        }
                    ],
                }
            }
          }
"""

import os
import sys
import copy
import six
import shutil
import json
import imp

from copy import deepcopy

from ansible import constants as C
from ansible.plugins.lookup import LookupBase
from ansible.module_utils.six import StringIO, iteritems, string_types
from ansible.module_utils.parsing.convert_bool import boolean
from ansible.utils.path import unfrackpath, makedirs_safe
from ansible.errors import AnsibleError

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display

    display = Display()

try:
    from pyang import plugin
    from pyang import statements
    from pyang import util
except ImportError:
    raise AnsibleError("pyang is not installed")


# The code to build the dependency tree from the instantiated tree that pyang has
# already parsed is referred from
# https://github.com/robshakir/pyangbind/blob/master/pyangbind/plugin/pybind.py
# and it is customised to fit in Ansible infra.

# After the dependency tree is build it is parsed to emit the Ansible spec and configuration schema
# in json format.
# Due to current structure of pybind plugin the referred code cannot be reused as it is
# or imported from pyangbind library.

def warning(msg):
    if C.ACTION_WARNINGS:
        display.warning(msg)


# Python3 support
if six.PY3:
    long = int
    unicode = str


# YANG is quite flexible in terms of what it allows as input to a boolean
# value, this map is used to provide a mapping of these values to the python
# True and False boolean instances.
class_bool_map = {
    'false': False,
    'False': False,
    'true': True,
    'True': True,
}

class_map = {
    # this map is dynamically built upon but defines how we take
    # a YANG type  and translate it into a native Python class
    # along with other attributes that are required for this mapping.
    #
    # key:                the name of the YANG type
    # native_type:        the Python class that is used to support this
    #                     YANG type natively.
    # map (optional):     a map to take input values and translate them
    #                     into valid values of the type.
    # base_type:          types that cannot be supported natively, such
    #                     as enumeration, or a string with a restriction placed on it)
    # quote_arg (opt):    whether the argument needs to be quoted (e.g., str("hello")) in
    #                     be quoted (e.g., str("hello")) in the code that is
    #                     output.
    # parent_type (opt):  for "derived" types, then we store what the enclosed
    #                     type is such that we can create instances where
    #                     required e.g., a restricted string will have a
    #                     parent_type of a string. this can be a list if the
    #                     type is a union.
    # restriction ...:    where the type is a restricted type, then the
    # (optional)          class_map dict entry can store more information about
    #                     the type of restriction.
    # Other types may add their own types to this dictionary that have
    # meaning only for themselves. For example, a ReferenceType can add the
    # path it references, and whether the require-instance keyword was set
    # or not.
    #
    'boolean': {
        "native_type": "boolean",
        "base_type": True,
        "quote_arg": True,
    },
    'binary': {
        "native_type": "bitarray",
        "base_type": True,
        "quote_arg": True
    },
    'uint8': {
        "native_type": "int",
        "base_type": True,
        "restriction_dict": {'min': 0, 'max': 255, 'int_size': 8}
    },
    'uint16': {
        "native_type": "int",
        "base_type": True,
        "restriction_dict": {'min': 0, 'max': 65535, 'int_size': 16}
    },
    'uint32': {
        "native_type": "int",
        "base_type": True,
        "restriction_dict": {'min': 0, 'max': 4294967295, 'int_size': 32}
    },
    'uint64': {
        "native_type": "long",
        "base_type": True,
        "restriction_dict": {'min': 0, 'max': 18446744073709551615, 'int_size': 64}
    },
    'string': {
        "native_type": "str",
        "base_type": True,
        "quote_arg": True
    },
    'decimal64': {
        "native_type": "float",
        "base_type": True,
    },
    'empty': {
        "native_type": "empty",
        "map": class_bool_map,
        "base_type": True,
        "quote_arg": True,
    },
    'int8': {
        "native_type": "int",
        "base_type": True,
        "restriction_dict": {'min': -128, 'max': 127, 'int_size': 8}
    },
    'int16': {
        "native_type": "int",
        "base_type": True,
        "restriction_dict": {'min': -32768, 'max': 32767, 'int_size': 16}
    },
    'int32': {
        "native_type": "int",
        "base_type": True,
        "restriction_dict": {'min': -2147483648, 'max': 2147483647, 'int_size': 32}
    },
    'int64': {
        "native_type": "long",
        "base_type": True,
        "restriction_dict": {'min': -9223372036854775808, 'max': 9223372036854775807, 'int_size': 64}
    },
}

# We have a set of types which support "range" statements in RFC6020. This
# list determins types that should be allowed to have a "range" argument.
INT_RANGE_TYPES = ["uint8", "uint16", "uint32", "uint64",
                   "int8", "int16", "int32", "int64"]

# The types that are built-in to YANG
YANG_BUILTIN_TYPES = list(class_map.keys()) + \
                     ["container", "list", "rpc", "notification", "leafref"]

YANG2SPEC_PLUGIN_PATH = "~/.ansible/tmp/yang2spec"

# Words that could turn up in YANG definition files that are actually
# reserved names in Python, such as being builtin types. This list is
# not complete, but will probably continue to grow.
reserved_name = ["list", "str", "int", "global", "decimal", "float",
                 "as", "if", "else", "elif", "map", "set", "class",
                 "from", "import", "pass", "return", "is", "exec",
                 "pop", "insert", "remove", "add", "delete", "local",
                 "get", "default", "yang_name", "def", "print", "del",
                 "break", "continue", "raise", "in", "assert", "while",
                 "for", "try", "finally", "with", "except", "lambda",
                 "or", "and", "not", "yield", "property", "min", "max"]

ansible_spec_header = {}
ansible_spec_option = {"options": {}}
ansible_spec_return = {"return": {}}


class LookupModule(LookupBase):
    VALID_FILE_EXTENSIONS = ('.yang',)

    def run(self, terms, variables=None, **kwargs):

        try:
            yang_file = terms[0]
        except IndexError:
            raise AnsibleError('the yang file must be specified')

        if not os.path.isfile(yang_file):
            raise AnsibleError('%s invalid file path' % yang_file)

        search_path = kwargs.pop('search_path', '')

        for path in search_path.split(':'):
            if path is not '' and not os.path.isdir(path):
                raise AnsibleError('%s is invalid directory path' % path)

        pyang_exec_path = find_file_in_path('pyang')

        pyang_exec = imp.load_source('pyang', pyang_exec_path)

        saved_arg = deepcopy(sys.argv)

        saved_stdout = sys.stdout
        sys.stdout = StringIO()

        plugin_file_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'yang2spec.py')

        plugindir = unfrackpath(YANG2SPEC_PLUGIN_PATH)
        makedirs_safe(plugindir)

        shutil.copy(plugin_file_src, plugindir)

        # fill in the sys args before invoking pyang
        sys.argv = [pyang_exec_path, '--plugindir', plugindir, '-f', 'yang2spec', yang_file, '-p', search_path]

        res = list()
        try:
            pyang_exec.run()
        except SystemExit:
            pass

        res.append(sys.stdout.getvalue())

        sys.argv = saved_arg
        sys.stdout = saved_stdout

        shutil.rmtree(plugindir, ignore_errors=True)
        return res


class Yang2Spec(plugin.PyangPlugin):
    def add_output_format(self, fmts):
        # Add the 'pybind' output format to pyang.
        self.multiple_modules = True
        fmts['yang2spec'] = self

    def emit(self, ctx, modules, fd):
        # When called, call the build_pyangbind function.
        build_spec(ctx, modules, fd)
        emit_ansible_spec(fd)

    def add_opts(self, optparser):
        # Add yang2spec specific operations to pyang.
        pass


def find_file_in_path(filename):
    # Check $PATH first, followed by same directory as sys.argv[0]
    paths = os.environ['PATH'].split(os.pathsep) + [os.path.dirname(sys.argv[0])]
    for dirname in paths:
        fullpath = os.path.join(dirname, filename)
        if os.path.isfile(fullpath):
            return fullpath


# Base machinery to support operation as a plugin to pyang.
def pyang_plugin_init():
    plugin.register_plugin(Yang2Spec())


def emit_ansible_spec(fd):
    output = {
        "spec": ansible_spec_option,
        "config_schema": emit_json_schema()
    }
    fd.write(json.dumps(output))


def parse_suboptions(config, suboptions):
    suboptions = suboptions.get('suboptions')
    type = suboptions.pop('suboptions_type', None)
    elements = suboptions.pop('suboptions_elements', None)

    for k, v in iteritems(suboptions):
        if type == 'list':
            config[k] = [{}]
        else:
            config[k] = {}
        if isinstance(v, dict):
            if v.get('suboptions'):
                if isinstance(config[k], list):
                    parse_suboptions(config[k][0], v)
                else:
                    parse_suboptions(config[k], v)
            else:
                parse_options(config, k, v)
        else:
            config[k] = v
    return config


def parse_options(config, name, spec):
    type = spec.get('type', 'str')
    if type == 'dict':
        config[name] = {}
    elif type == 'list':
        config[name] = []
    else:
        config[name] = None

    default = spec.get('default')
    if default:
        if type in ('int', 'long'):
            config[name] = int(default)
        elif type in ('float',):
            config[name] = float(default)
        elif type in ('boolean',):
            config[name] = boolean(default)
        else:
            config[name] = default


def emit_json_schema():
    options_spec = deepcopy(ansible_spec_option)
    options = options_spec.get('options')
    config = {}
    for k, v in iteritems(options):
        config[k] = {}
        if v.get('suboptions'):
            parse_suboptions(config[k], v)
        else:
            parse_options(config, k, v)
    return config


def safe_name(arg):
    """
      Make a leaf or container name safe for use in Python.
    """
    arg = arg.replace("-", "_")
    arg = arg.replace(".", "_")
    if arg in reserved_name:
        arg += "_"
    # store the unsafe->original version mapping
    # so that we can retrieve it when get() is called.
    return arg


def module_import_prefixes(ctx):
    mod_ref_prefixes = {}
    for mod in ctx.modules:
        m = ctx.search_module(0, mod[0])
        for importstmt in m.search('import'):
            if not importstmt.arg in mod_ref_prefixes:
                mod_ref_prefixes[importstmt.arg] = []
            mod_ref_prefixes[importstmt.arg].append(importstmt.search_one('prefix').arg)
    return mod_ref_prefixes


def find_child_definitions(obj, defn, prefix, definitions):
    for i in obj.search(defn):
        if i.arg in definitions:
            sys.stderr.write("WARNING: duplicate definition of %s" % i.arg)
        else:
            definitions["%s:%s" % (prefix, i.arg)] = i

    possible_parents = [
        'grouping', 'container',
        'list', 'rpc', 'input',
        'output', 'notification'
    ]

    for parent_type in possible_parents:
        for ch in obj.search(parent_type):
            if ch.i_children:
                find_child_definitions(ch, defn, prefix, definitions)

    return definitions


def find_definitions(defn, ctx, module, prefix):
    # Find the statements within a module that map to a particular type of
    # statement, for instance - find typedefs, or identities, and reutrn them
    # as a dictionary to the calling function.
    definitions = {}
    return find_child_definitions(module, defn, prefix, definitions)


class Identity(object):
    def __init__(self, name):
        self.name = name
        self.source_module = None
        self._imported_prefixes = []
        self.source_namespace = None
        self.base = None
        self.children = []

    def add_prefix(self, prefix):
        if not prefix in self._imported_prefixes:
            self._imported_prefixes.append(prefix)

    def add_child(self, child):
        if not isinstance(child, Identity):
            raise ValueError("Must supply a identity as a child")
        self.children.append(child)

    def __str__(self):
        return "%s:%s" % (self.source_module, self.name)

    def prefixes(self):
        return self._imported_prefixes


class IdentityStore(object):
    def __init__(self):
        self._store = []

    def find_identity_by_source_name(self, s, n):
        for i in self._store:
            if i.source_module == s and i.name == n:
                return i

    def add_identity(self, i):
        if isinstance(i, Identity):
            if not self.find_identity_by_source_name(i.source_module, i.name):
                self._store.append(i)
        else:
            raise ValueError("Must specify an identity")

    def identities(self):
        return ["%s:%s" % (i.source_module, i.name) for i in self._store]

    def __iter__(self):
        return iter(self._store)

    def build_store_from_definitions(self, ctx, defnd):
        unresolved_identities = list(defnd.keys())
        unresolved_identity_count = {k: 0 for k in defnd}
        error_ids = []

        mod_ref_prefixes = module_import_prefixes(ctx)

        while len(unresolved_identities):
            this_id = unresolved_identities.pop(0)
            iddef = defnd[this_id]

            base = iddef.search_one('base')
            try:
                mainmod = iddef.main_module()
            except AttributeError:
                mainmod = None
            if mainmod is not None:
                defmod = mainmod

            defining_module = defmod.arg
            namespace = defmod.search_one('namespace').arg
            prefix = defmod.search_one('prefix').arg

            if base is None:
                # Add a new identity which can be a base
                tid = Identity(iddef.arg)
                tid.source_module = defining_module
                tid.source_namespace = namespace
                tid.add_prefix(prefix)
                self.add_identity(tid)

                if defining_module in mod_ref_prefixes:
                    for i in mod_ref_prefixes[defining_module]:
                        tid.add_prefix(i)

            else:
                # Determine what the name of the base and the prefix for
                # the base should be
                if ":" in base.arg:
                    base_pfx, base_name = base.arg.split(":")
                else:
                    base_pfx, base_name = prefix, base.arg

                parent_module = util.prefix_to_module(defmod, base_pfx,
                                                      base.pos, ctx.errors)

                # Find whether we have the base in the store
                base_id = self.find_identity_by_source_name(parent_module.arg, base_name)

                if base_id is None:
                    # and if not, then push this identity back onto the stack
                    unresolved_identities.append(this_id)
                    unresolved_identity_count[this_id] += 1
                else:
                    # Check we don't already have this identity defined
                    if self.find_identity_by_source_name(defining_module, iddef.arg) is None:
                        # otherwise, create a new identity that reflects this one
                        tid = Identity(iddef.arg)
                        tid.source_module = defining_module
                        tid.source_namespace = namespace
                        tid.add_prefix(prefix)
                        base_id.add_child(tid)
                        self.add_identity(tid)

                        if defining_module in mod_ref_prefixes:
                            for i in mod_ref_prefixes[defining_module]:
                                tid.add_prefix(i)

            if error_ids:
                raise TypeError("could not resolve identities %s" % error_ids)

        self._build_inheritance()

    def _recurse_children(self, identity, children):
        for child in identity.children:
            children.append(child)
            self._recurse_children(child, children)
        return children

    def _build_inheritance(self):
        for i in self._store:
            ch = list()
            self._recurse_children(i, ch)
            i.children = ch


# Core function to build the Ansible spec output - starting with building the
# dependencies - and then working through the instantiated tree that pyang has
# already parsed.
def build_spec(ctx, modules, fd):
    # Restrict the output of the plugin to only the modules that are supplied
    # to pyang.
    module_d = {}
    for mod in modules:
        module_d[mod.arg] = mod
    pyang_called_modules = module_d.keys()

    # Bail if there are pyang errors, since this certainly means that the
    # output will fail - unless these are solely due to imports that
    # we provided but then unused.
    if len(ctx.errors):
        for e in ctx.errors:
            display.display("INFO: encountered %s" % str(e))
            if not e[1] in ["UNUSED_IMPORT", "PATTERN_ERROR"]:
                raise AnsibleError("FATAL: yang2spec cannot build module that pyang" +
                                 " has found errors with.\n")

    # Determine all modules, and submodules that are needed, along with the
    # prefix that is used for it. We need to ensure that we understand all of the
    # prefixes that might be used to reference an identity or a typedef.
    all_mods = []
    for module in modules:
        local_module_prefix = module.search_one('prefix')
        if local_module_prefix is None:
            local_module_prefix = \
                module.search_one('belongs-to').search_one('prefix')
            if local_module_prefix is None:
                raise AttributeError("A module (%s) must have a prefix or parent " +
                                     "module")
            local_module_prefix = local_module_prefix.arg
        else:
            local_module_prefix = local_module_prefix.arg
        mods = [(local_module_prefix, module)]

        imported_modules = module.search('import')

        # 'include' statements specify the submodules of the existing module -
        # that also need to be parsed.
        for i in module.search('include'):
            subm = ctx.get_module(i.arg)
            if subm is not None:
                mods.append((local_module_prefix, subm))
                # Handle the case that imports are within a submodule
                if subm.search('import') is not None:
                    imported_modules.extend(subm.search('import'))

        # 'import' statements specify the other modules that this module will
        # reference.
        for j in imported_modules:
            mod = ctx.get_module(j.arg)
            if mod is not None:
                imported_module_prefix = j.search_one('prefix').arg
                mods.append((imported_module_prefix, mod))
                modules.append(mod)
        all_mods.extend(mods)

    # remove duplicates from the list (same module and prefix)
    new_all_mods = []
    for mod in all_mods:
        if mod not in new_all_mods:
            new_all_mods.append(mod)
    all_mods = new_all_mods

    # Build a list of the 'typedef' and 'identity' statements that are included
    # in the modules supplied.
    defn = {}
    for defnt in ['typedef', 'identity']:
        defn[defnt] = {}
        for m in all_mods:
            t = find_definitions(defnt, ctx, m[1], m[0])
            for k in t:
                if k not in defn[defnt]:
                    defn[defnt][k] = t[k]

    # Build the identities and typedefs (these are added to the class_map which
    # is globally referenced).
    build_identities(ctx, defn['identity'])
    build_typedefs(ctx, defn['typedef'])

    # Iterate through the tree which pyang has built, solely for the modules
    # that pyang was asked to build
    for modname in pyang_called_modules:
        module = module_d[modname]
        mods = [module]
        for i in module.search('include'):
            subm = ctx.get_module(i.arg)
            if subm is not None:
                mods.append(subm)
        for m in mods:
            children = [ch for ch in module.i_children
                        if ch.keyword in statements.data_definition_keywords]
            get_children(ctx, fd, children, m, m)


def build_identities(ctx, defnd):
    # Build a storage object that has all the definitions that we
    # require within it.
    idstore = IdentityStore()
    idstore.build_store_from_definitions(ctx, defnd)

    identity_dict = {}
    for identity in idstore:
        for prefix in identity.prefixes():
            ident = "%s:%s" % (prefix, identity.name)
            identity_dict[ident] = {}
            identity_dict["%s" % identity.name] = {}
            for ch in identity.children:
                d = {"@module": ch.source_module, "@namespace": ch.source_namespace}
                for cpfx in ch.prefixes() + [None]:
                    if cpfx is not None:
                        spfx = "%s:" % cpfx
                    else:
                        spfx = ""
                    identity_dict[ident][ch.name] = d
                    identity_dict[identity.name][ch.name] = d
                    identity_dict[ident]["%s%s" % (spfx, ch.name)] = d
                    identity_dict[identity.name]["%s%s" % (spfx, ch.name)] = d

        if not identity.name in identity_dict:
            identity_dict[identity.name] = {}

    # Add entries to the class_map such that this identity can be referenced by
    # elements that use this identity ref.
    for i in identity_dict:
        id_type = {"native_type": "identity",
                   "restriction_argument": identity_dict[i],
                   "restriction_type": "dict_key",
                   "parent_type": "string",
                   "base_type": False}
        class_map[i] = id_type


def build_typedefs(ctx, defnd):
    # Build the type definitions that are specified within a model. Since
    # typedefs are essentially derived from existing types, order of processing
    # is important - we need to go through and build the types in order where
    # they have a known 'type'.
    unresolved_tc = {}
    for i in defnd:
        unresolved_tc[i] = 0
    unresolved_t = list(defnd.keys())
    error_ids = []
    known_types = list(class_map.keys())
    known_types.append('enumeration')
    known_types.append('leafref')
    base_types = copy.deepcopy(known_types)
    process_typedefs_ordered = []

    while len(unresolved_t):
        t = unresolved_t.pop(0)
        base_t = defnd[t].search_one('type')
        if base_t.arg == "union":
            subtypes = []
            for i in base_t.search('type'):
                if i.arg == "identityref":
                    subtypes.append(i.search_one('base'))
                else:
                    subtypes.append(i)
        elif base_t.arg == "identityref":
            subtypes = [base_t.search_one('base')]
        else:
            subtypes = [base_t]

        any_unknown = False
        for i in subtypes:
            # Resolve this typedef to the module that it
            # was defined by

            if ":" in i.arg:
                defining_module = util.prefix_to_module(defnd[t].i_module,
                                                        i.arg.split(":")[0], defnd[t].pos, ctx.errors)
            else:
                defining_module = defnd[t].i_module

            belongs_to = defining_module.search_one('belongs-to')
            if belongs_to is not None:
                for mod in ctx.modules:
                    if mod[0] == belongs_to.arg:
                        defining_module = ctx.modules[mod]

            real_pfx = defining_module.search_one('prefix').arg

            if ":" in i.arg:
                tn = u"%s:%s" % (real_pfx, i.arg.split(":")[1])
            elif i.arg not in base_types:
                # If this was not a base type (defined in YANG) then resolve it
                # to the module it belongs to.
                tn = u"%s:%s" % (real_pfx, i.arg)
            else:
                tn = i.arg

            if tn not in known_types:
                any_unknown = True

        if not any_unknown:
            process_typedefs_ordered.append((t, defnd[t]))
            known_types.append(t)
        else:
            unresolved_tc[t] += 1
            if unresolved_tc[t] > 1000:
                # Take a similar approach to the resolution of identities. If we have a
                # typedef that has a type in it that is not found after many iterations
                # then we should bail.
                error_ids.append(t)
                sys.stderr.write("could not find a match for %s type -> %s\n" %
                                 (t, [i.arg for i in subtypes]))
            else:
                unresolved_t.append(t)

    if error_ids:
        raise TypeError("could not resolve typedefs %s" % error_ids)

    # Process the types that we built above.
    for i_tuple in process_typedefs_ordered:
        item = i_tuple[1]
        type_name = i_tuple[0]
        mapped_type = False
        restricted_arg = False
        # Copy the class_map entry - this is done so that we do not alter the
        # existing instance in memory as we add to it.
        cls, elemtype = copy.deepcopy(build_elemtype(ctx, item.search_one('type')))
        known_types = list(class_map.keys())
        # Enumeration is a native type, but is not natively supported
        # in the class_map, and hence we append it here.
        known_types.append("enumeration")
        known_types.append("leafref")

        # Don't allow duplicate definitions of types
        if type_name in known_types:
            raise TypeError("Duplicate definition of %s" % type_name)
        default_stmt = item.search_one('default')

        # 'elemtype' is a list when the type includes a union, so we need to go
        # through and build a type definition that supports multiple types.
        if not isinstance(elemtype, list):
            restricted = False
            # Map the original type to the new type, parsing the additional arguments
            # that may be specified, for example, a new default, a pattern that must
            # be matched, or a length (stored in the restriction_argument, and
            # restriction_type class_map variables).
            class_map[type_name] = {"base_type": False}
            class_map[type_name]["native_type"] = elemtype["native_type"]
            if "parent_type" in elemtype:
                class_map[type_name]["parent_type"] = elemtype["parent_type"]
            else:
                yang_type = item.search_one('type').arg
                if yang_type not in known_types:
                    raise TypeError("typedef specified a native type that was not " +
                                    "supported")
                class_map[type_name]["parent_type"] = yang_type
            if default_stmt is not None:
                class_map[type_name]["default"] = default_stmt.arg
            if "referenced_path" in elemtype:
                class_map[type_name]["referenced_path"] = elemtype["referenced_path"]
                class_map[type_name]["class_override"] = "leafref"
            if "require_instance" in elemtype:
                class_map[type_name]["require_instance"] = elemtype["require_instance"]
            if "restriction_type" in elemtype:
                class_map[type_name]["restriction_type"] = \
                    elemtype["restriction_type"]
                class_map[type_name]["restriction_argument"] = \
                    elemtype["restriction_argument"]
            if "quote_arg" in elemtype:
                class_map[type_name]["quote_arg"] = elemtype["quote_arg"]
        else:
            # Handle a typedef that is a union - extended the class_map arguments
            # to be a list that is parsed by the relevant dynamic type generation
            # function.
            native_type = []
            parent_type = []
            default = False if default_stmt is None else default_stmt.arg
            for i in elemtype:

                if isinstance(i[1]["native_type"], list):
                    native_type.extend(i[1]["native_type"])
                else:
                    native_type.append(i[1]["native_type"])

                if i[1]["yang_type"] in known_types:
                    parent_type.append(i[1]["yang_type"])
                elif i[1]["yang_type"] == "identityref":
                    parent_type.append(i[1]["parent_type"])
                else:
                    msg = "typedef in a union specified a native type that was not"
                    msg += " supported (%s in %s)" % (i[1]["yang_type"], item.arg)
                    raise TypeError(msg)

                if "default" in i[1] and not default:
                    # When multiple 'default' values are specified within a union that
                    # is within a typedef, then it will choose the first one.
                    q = True if "quote_arg" in i[1] else False
                    default = (i[1]["default"], q)
            class_map[type_name] = {"native_type": native_type, "base_type": False,
                                    "parent_type": parent_type}
            if default:
                class_map[type_name]["default"] = default[0]
                class_map[type_name]["quote_default"] = default[1]

        class_map[type_name.split(":")[1]] = class_map[type_name]


def get_children(ctx, fd, i_children, module, parent, path=str(),
                 parent_cfg=True, choice=False, register_paths=True):
    # Iterative function that is called for all elements that have childen
    # data nodes in the tree. This function resolves those nodes into the
    # relevant leaf, or container/list configuration and outputs the python
    # code that corresponds to it to the relevant file. parent_cfg is used to
    # ensure that where a parent container was set to config false, this is
    # inherited by all elements below it; and choice is used to store whether
    # these leaves are within a choice or not.
    used_types, elements = [], []
    choices = False

    # If we weren't asked to split the files, then just use the file handle
    # provided.
    nfd = fd

    if parent_cfg:
        # The first time we find a container that has config false set on it
        # then we need to hand this down the tree - we don't need to look if
        # parent_cfg has already been set to False as we need to inherit.
        parent_config = parent.search_one('config')
        if parent_config is not None:
            parent_config = parent_config.arg
            if parent_config.upper() == "FALSE":
                # this container is config false
                parent_cfg = False

    for ch in i_children:
        children_tmp = getattr(ch, "i_children", None)
        if children_tmp is not None:
            children_tmp = [i.arg for i in children_tmp]
        if ch.keyword == "choice":
            for choice_ch in ch.i_children:
                # these are case statements
                for case_ch in choice_ch.i_children:
                    elements += get_element(ctx, fd, case_ch, module, parent,
                                            path + "/" + case_ch.arg, parent_cfg=parent_cfg,
                                            choice=(ch.arg, choice_ch.arg), register_paths=register_paths)
        else:
            elements += get_element(ctx, fd, ch, module, parent, path + "/" + ch.arg,
                                    parent_cfg=parent_cfg, choice=choice, register_paths=register_paths)

    # 'container', 'module', 'list' and 'submodule' all have their own classes
    # generated.
    if parent.keyword in ["container", "module", "list", "submodule", "input",
                          "output", "rpc", "notification"]:

        if path == "" and ansible_spec_header.get('module_name') is None:
            ansible_spec_header['module_name'] = safe_name(parent.arg)

            parent_descr = parent.search_one('description')
            if parent_descr is not None:
                ansible_spec_header['description'] = parent_descr.arg.decode('utf8').encode('ascii',
                                                                                            'ignore').strip().replace(
                    '\n', ' ')
                ansible_spec_header['short_description'] = ansible_spec_header['description'].split('.')[0]
            else:
                ansible_spec_header['description'] = ""
                ansible_spec_header['short_description'] = ""

            ansible_spec_header['ansible_metadata'] = dict(metadata_version=1.1,
                                                           status=['preview'],
                                                           supported_by='network')

        # If the container is actually a list, then determine what the key value
        # is and store this such that we can give a hint.
        keyval = False
        if parent.keyword == "list":
            keyval = parent.search_one('key').arg if parent.search_one('key') \
                                                     is not None else False
            if keyval and " " in keyval:
                keyval = keyval.split(" ")
            else:
                keyval = [keyval]

    else:
        raise TypeError("unhandled keyword with children %s at %s" %
                        (parent.keyword, parent.pos))

    if len(elements) == 0:
        pass
    else:
        for i in elements:
            if i['yang_name'] == 'peer-type':
                pass
            if i["config"] and parent_cfg:
                spec = ansible_spec_option["options"]
            else:
                spec = ansible_spec_return["return"]

            default_arg = None
            if "default" in i and not i["default"] is None:
                default_arg = "\"%s\"" % (i["default"]) if i["quote_arg"] else "%s" \
                                                                               % i["default"]
            if i["class"] in ("leaf", "leaf-list"):
                spec = get_node_dict(i, spec)

                if default_arg is not None:
                    spec['default'] = default_arg

                if i.get('type'):
                    spec['type'] = i['type']

                if i.get('restriction_argument'):
                    spec['restriction'] = i['restriction_argument']
                    spec['restriction_type'] = i.get('restriction_type')
                elif i.get('restriction_dict'):
                    spec['restriction'] = i['restriction_dict']

                if i.get('default'):
                    spec['default'] = i['default']

                if i.get('description'):
                    spec['description'] = i["description"].decode('utf-8').encode('ascii', 'ignore').replace('\n', ' ')

                if keyval and i['yang_name'] in keyval:
                    spec['required'] = True

                if i.get("class") == "leaf-list":
                    spec['elements'] = spec['type']
                    spec['type'] = 'list'

            elif i["class"] == "container":
                spec = get_node_dict(i, spec)
                if i.get('presence'):
                    spec['presence'] = True

            elif i["class"] == "list":
                spec = get_node_dict(i, spec)
                spec['suboptions_type'] = 'list'
                spec['suboptions_elements'] = 'dict'

    return None


def build_elemtype(ctx, et, prefix=False):
    # Build a dictionary which defines the type for the element. This is used
    # both in the case that a typedef needs to be built, as well as on per-list
    # basis.
    cls = None
    pattern_stmt = et.search_one('pattern') if not et.search_one('pattern') \
                                                   is None else False
    range_stmt = et.search_one('range') if not et.search_one('range') \
                                               is None else False
    length_stmt = et.search_one('length') if not et.search_one('length') \
                                                 is None else False

    # Determine whether there are any restrictions that are placed on this leaf,
    # and build a dictionary of the different restrictions to be placed on the
    # type.
    restrictions = {}
    if pattern_stmt:
        restrictions['pattern'] = pattern_stmt.arg

    if length_stmt:
        if "|" in length_stmt.arg:
            restrictions['length'] = [i.replace(' ', '') for i in
                                      length_stmt.arg.split("|")]
        else:
            restrictions['length'] = [length_stmt.arg]

    if range_stmt:
        # Complex ranges are separated by pipes
        if "|" in range_stmt.arg:
            restrictions['range'] = [i.replace(' ', '') for i in
                                     range_stmt.arg.split("|")]
        else:
            restrictions['range'] = [range_stmt.arg]

    # Build RestrictedClassTypes based on the compiled dictionary and the
    # underlying base type.
    if len(restrictions):
        if 'length' in restrictions or 'pattern' in restrictions:
            cls = "restricted-%s" % (et.arg)
            elemtype = {
                "native_type": class_map[et.arg]["native_type"],
                "restriction_dict": restrictions,
                "parent_type": et.arg,
                "base_type": False,
            }
        elif 'range' in restrictions:
            cls = "restricted-%s" % et.arg
            elemtype = {
                "native_type": class_map[et.arg]["native_type"],
                "restriction_dict": restrictions,
                "parent_type": et.arg,
                "base_type": False,
            }

    # Handle all other types of leaves that are not restricted classes.
    if cls is None:
        cls = "leaf"
        if et.arg == "enumeration":
            enumeration_dict = {}
            for enum in et.search('enum'):
                enumeration_dict[unicode(enum.arg)] = {}
                val = enum.search_one('value')
                if val is not None:
                    enumeration_dict[unicode(enum.arg)]["value"] = int(val.arg)
            elemtype = {"native_type": "enumeration",
                        "restriction_argument": enumeration_dict,
                        "restriction_type": "dict_key",
                        "parent_type": "string",
                        "base_type": False}

        # Map decimal64 to a RestrictedPrecisionDecimalType - this is there to
        # ensure that the fraction-digits argument can be implemented. Note that
        # fraction-digits is a mandatory argument.
        elif et.arg == "decimal64":
            fd_stmt = et.search_one('fraction-digits')
            if fd_stmt is not None:
                cls = "restricted-decimal64"
                elemtype = {"native_type": fd_stmt.arg,
                            "base_type": False,
                            "parent_type": "decimal64"}
            else:
                elemtype = class_map[et.arg]
        # Handle unions - build a list of the supported types that are under the
        # union.
        elif et.arg == "union":
            elemtype = []
            for uniontype in et.search('type'):
                elemtype_s = copy.deepcopy(build_elemtype(ctx, uniontype))
                elemtype_s[1]["yang_type"] = uniontype.arg
                elemtype.append(elemtype_s)
            cls = "union"
        # Map leafrefs to a ReferenceType, handling the referenced path, and
        # whether require-instance is set. When xpathhelper is not specified, then
        # no such mapping is done - at this point, we solely map to a string.
        elif et.arg == "leafref":
            path_stmt = et.search_one('path')
            if path_stmt is None:
                raise ValueError("leafref specified with no path statement")
            require_instance = \
                class_bool_map[et.search_one('require-instance').arg] \
                    if et.search_one('require-instance') \
                       is not None else True

            elemtype = {
                "native_type": "unicode",
                "parent_type": "string",
                "base_type": False,
            }
        # Handle identityrefs, but check whether there is a valid base where this
        # has been specified.
        elif et.arg == "identityref":
            base_stmt = et.search_one('base')
            if base_stmt is None:
                raise ValueError("identityref specified with no base statement")
            try:
                elemtype = class_map[base_stmt.arg]
            except KeyError:
                display.debug(class_map.keys())
                display.debug(et.arg)
                display.debug(base_stmt.arg)
                raise AnsibleError("FATAL: identityref with an unknown base\n")
        else:
            # For all other cases, then we should be able to look up directly in the
            # class_map for the defined type, since these are not 'derived' types
            # at this point. In the case that we are referencing a type that is a
            # typedef, then this has been added to the class_map.
            try:
                elemtype = class_map[et.arg]
            except KeyError:
                passed = False
                if prefix:
                    try:
                        tmp_name = "%s:%s" % (prefix, et.arg)
                        elemtype = class_map[tmp_name]
                        passed = True
                    except:
                        pass
                if passed is False:
                    display.debug(class_map.keys())
                    display.debug(et.arg)
                    display.debug(prefix)
                    raise AnsibleError("FATAL: unmapped type (%s)\n" % (et.arg))

        if isinstance(elemtype, list):
            cls = "leaf-union"
        elif "class_override" in elemtype:
            # this is used to propagate the fact that in some cases the
            # native type needs to be dynamically built (e.g., leafref)
            cls = elemtype["class_override"]

    return cls, elemtype


def find_absolute_default_type(default_type, default_value, elemname):
    if not isinstance(default_type, list):
        return default_type

    for i in default_type:
        if not i[1]["base_type"]:
            test_type = class_map[i[1]["parent_type"]]
        else:
            test_type = i[1]
        try:
            default_type = test_type
            break
        except (ValueError, TypeError):
            pass
    return find_absolute_default_type(default_type, default_value, elemname)


def get_node_dict(element, spec):
    xpath = element["path"]
    if xpath.startswith('/'):
        xpath = xpath[1:]

    xpath = xpath.split('/')
    xpath_len = len(xpath)
    for index, item in enumerate(xpath):
        if item not in spec.keys():
            if index == (xpath_len - 1):
                spec[item] = dict()
                spec = spec[item]
            else:
                spec[item] = dict()
                spec[item]['suboptions'] = dict()
                spec = spec[item]['suboptions']
        else:
            spec = spec[item]['suboptions'] if 'suboptions' in spec[item] else spec[item]
    return spec


def get_element(ctx, fd, element, module, parent, path,
                parent_cfg=True, choice=False, register_paths=True):
    # Handle mapping of an invidual element within the model. This function
    # produces a dictionary that can then be mapped into the relevant code that
    # dynamically generates a class.

    # Find element's namespace and defining module
    # If the element has the "main_module" attribute then it is part of a
    # submodule and hence we should check the namespace and defining module
    # of this, rather than the submodule
    if hasattr(element, "main_module"):
        element_module = element.main_module()
    elif hasattr(element, "i_orig_module"):
        element_module = element.i_orig_module
    else:
        element_module = None

    namespace = element_module.search_one("namespace").arg if \
        element_module.search_one("namespace") is not None else \
        None
    defining_module = element_module.arg

    this_object = []
    default = False
    has_children = False
    create_list = False

    elemdescr = element.search_one('description')
    if elemdescr is None:
        elemdescr = False
    else:
        elemdescr = elemdescr.arg

    # If the element has an i_children attribute then this is a container, list
    # leaf-list or choice. Alternatively, it can be the 'input' or 'output'
    # substmts of an RPC or a notification
    if hasattr(element, 'i_children'):
        if element.keyword in ["container", "list", "input", "output", "notification"]:
            has_children = True
        elif element.keyword in ["leaf-list"]:
            create_list = True

        # Fixup the path when within a choice, because this iteration belives that
        # we are under a new container, but this does not exist in the path.
        if element.keyword in ["choice"]:
            path_parts = path.split("/")
            npath = ""
            for i in range(0, len(path_parts) - 1):
                npath += "%s/" % path_parts[i]
            npath.rstrip("/")
        else:
            npath = path

        # Create an element for a container.
        if element.i_children:
            chs = element.i_children
            has_presence = True if element.search_one('presence') is not None else False
            if has_presence is False and len(chs) == 0:
                return []

            get_children(ctx, fd, chs, module, element, npath, parent_cfg=parent_cfg,
                         choice=choice, register_paths=register_paths)

            elemdict = {
                "name": safe_name(element.arg), "origtype": element.keyword,
                "class": element.keyword,
                "path": safe_name(npath), "config": True,
                "description": elemdescr,
                "yang_name": element.arg,
                "choice": choice,
                "register_paths": register_paths,
                "namespace": namespace,
                "defining_module": defining_module,
                "presence": has_presence,
            }

            # Otherwise, give a unique name for the class within the dictionary.
            elemdict["type"] = "%s_%s_%s" % (safe_name(element.arg),
                                             safe_name(module.arg),
                                             safe_name(path.replace("/", "_")))

            # Deal with specific cases for list - such as the key and how it is
            # ordered.
            if element.keyword == "list":
                elemdict["key"] = safe_name(element.search_one("key").arg) \
                    if element.search_one("key") is not None else False
                elemdict["yang_keys"] = element.search_one("key").arg \
                    if element.search_one("key") is not None else False
                user_ordered = element.search_one('ordered-by')
                elemdict["user_ordered"] = True if user_ordered is not None \
                                                   and user_ordered.arg.upper() == "USER" else False
            this_object.append(elemdict)
            has_children = True

    # Deal with the cases that the attribute does not have children.
    if not has_children:
        if element.keyword in ["leaf-list"]:
            create_list = True
        cls, elemtype = copy.deepcopy(build_elemtype(ctx,
                                                     element.search_one('type')))

        # Determine what the default for the leaf should be where there are
        # multiple available.
        # Algorithm:
        #   - build a tree that is rooted on this class.
        #   - perform a breadth-first search - the first node found
        #   - that has the "default" leaf set, then we take this
        #     as the value for the default

        # then starting at the selected default node, traverse
        # until we find a node that is declared to be a base_type
        elemdefault = element.search_one('default')
        default_type = False
        quote_arg = False
        if elemdefault is not None:
            elemdefault = elemdefault.arg
            default_type = elemtype
        if isinstance(elemtype, list):
            # this is a union, we should check whether any of the types
            # immediately has a default
            for i in elemtype:
                if "default" in i[1]:
                    elemdefault = i[1]["default"]
                    default_type = i[1]
        elif "default" in elemtype:
            # if the actual type defines the default, then we need to maintain
            # this
            elemdefault = elemtype["default"]
            default_type = elemtype

        # we need to indicate that the default type for the class_map
        # is str
        tmp_class_map = copy.deepcopy(class_map)
        tmp_class_map["enumeration"] = {"parent_type": "string"}

        if not default_type:
            if isinstance(elemtype, list):
                # this type has multiple parents
                for i in elemtype:
                    if "parent_type" in i[1]:
                        if isinstance(i[1]["parent_type"], list):
                            to_visit = [j for j in i[1]["parent_type"]]
                        else:
                            to_visit = [i[1]["parent_type"]]
            elif "parent_type" in elemtype:
                if isinstance(elemtype["parent_type"], list):
                    to_visit = [i for i in elemtype["parent_type"]]
                else:
                    to_visit = [elemtype["parent_type"]]

                checked = list()
                while to_visit:
                    check = to_visit.pop(0)
                    if check not in checked:
                        checked.append(check)
                        if "parent_type" in tmp_class_map[check]:
                            if isinstance(tmp_class_map[check]["parent_type"], list):
                                to_visit.extend(tmp_class_map[check]["parent_type"])
                            else:
                                to_visit.append(tmp_class_map[check]["parent_type"])

                # checked now has the breadth-first search result
                if elemdefault is None:
                    for option in checked:
                        if "default" in tmp_class_map[option]:
                            elemdefault = tmp_class_map[option]["default"]
                            default_type = tmp_class_map[option]
                            break

        if elemdefault is not None:
            # we now need to check whether there's a need to
            # find out what the base type is for this type
            # we really expect a linear chain here.

            # if we have a tuple as the type here, this means that
            # the default was set at a level where there was not
            # a single option for the type. check the default
            # against each option, to get a to a single default_type
            if isinstance(default_type, list):
                default_type = find_absolute_default_type(default_type, elemdefault,
                                                          element.arg)

            if not default_type["base_type"]:
                if "parent_type" in default_type:
                    if isinstance(default_type["parent_type"], list):
                        to_visit = [i for i in default_type["parent_type"]]
                    else:
                        to_visit = [default_type["parent_type"]]
                checked = list()
                while to_visit:
                    check = to_visit.pop(0)  # remove from the top of stack - depth first
                    if check not in checked:
                        checked.append(check)
                        if "parent_type" in tmp_class_map[check]:
                            if isinstance(tmp_class_map[check]["parent_type"], list):
                                to_visit.extend(tmp_class_map[check]["parent_type"])
                            else:
                                to_visit.append(tmp_class_map[check]["parent_type"])
                default_type = tmp_class_map[checked.pop()]
                if not default_type["base_type"]:
                    raise TypeError("default type was not a base type")

        # Set the default type based on what was determined above about the
        # correct value to set.
        if default_type:
            quote_arg = default_type["quote_arg"] if "quote_arg" in \
                                                     default_type else False
            default_type = default_type["native_type"]

        elemconfig = class_bool_map[element.search_one('config').arg] if \
            element.search_one('config') else True

        elemname = safe_name(element.arg)

        # Deal with the cases that there is a requirement to create a list - these
        # are leaf lists. There is some special handling for leaf-lists to ensure
        # that the references are correctly created.
        if create_list:
            if not cls == "leafref":
                cls = "leaf-list"

                if isinstance(elemtype, list):
                    c = 0
                    allowed_types = []
                    for subtype in elemtype:
                        # nested union within a leaf-list type
                        if isinstance(subtype, tuple):
                            if subtype[0] == "leaf-union":
                                for subelemtype in subtype[1]["native_type"]:
                                    allowed_types.append(subelemtype)
                            else:
                                if isinstance(subtype[1]["native_type"], list):
                                    allowed_types.extend(subtype[1]["native_type"])
                                else:
                                    allowed_types.append(subtype[1]["native_type"])
                        else:
                            allowed_types.append(subtype["native_type"])
                else:
                    allowed_types = elemtype["native_type"]
            else:
                cls = "leafref-list"
                allowed_types = {
                    "native_type": elemtype["native_type"],
                    "referenced_path": elemtype["referenced_path"],
                    "require_instance": elemtype["require_instance"],
                }
            elemntype = {"class": cls, "native_type": ("TypedListType",
                                                       allowed_types)}

        else:
            if cls == "union" or cls == "leaf-union":
                elemtype = {"class": cls, "native_type": ("UnionType", elemtype)}
            elemntype = elemtype["native_type"]

        # Build the dictionary for the element with the relevant meta-data
        # specified within it.
        elemdict = {
            "name": elemname, "type": elemntype,
            "origtype": element.search_one('type').arg, "path":
                safe_name(path),
            "class": cls, "default": elemdefault,
            "config": elemconfig, "defaulttype": default_type,
            "quote_arg": quote_arg,
            "description": elemdescr, "yang_name": element.arg,
            "choice": choice,
            "register_paths": register_paths,
            "namespace": namespace,
            "defining_module": defining_module,
            "restriction_dict": elemtype.get('restriction_dict'),
            "restriction_type": elemtype.get('restriction_type'),
            "restriction_argument": elemtype.get('restriction_argument'),
        }

        if cls == "leafref":
            elemdict["referenced_path"] = elemtype["referenced_path"]
            elemdict["require_instance"] = elemtype["require_instance"]

        this_object.append(elemdict)
    return this_object
