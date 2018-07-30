# (c) 2018 Red Hat, Inc.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = """
lookup: yang_json2xml
author: Ansible Network
version_added: "2.6"
short_description: Validates json configuration against yang data model and convert it to xml.
description:
  - This plugin lookups the input json configuration, validates it against the respective yang data
    model which is also given as input to this plugin and coverts it to xml format which can be used
    as payload within Netconf rpc.
options:
  _terms:
    description:
      - Input json configuration file path that adheres to a particular yang model.
    required: True
    type: path
  root:
    description:
      - Specifies the target root node of the generated xml. The default value is C(config)
    default: config
  yang_file:
    description:
      - Path to yang model file against which the json configuration is validated and
        converted to xml.
    required: True
    type: path
  search_path:
    description:
      - This option is a colon C(:) separated list of directories to search for imported yang modules
        in the yang file mentioned in C(path) option. If the value is not given it will search in
        the current directory.
    required: false
"""

EXAMPLES = """
- name: translate json to xml
  debug: msg="{{ lookup('yang_json2xml', config_json, yang_file='openconfig/public/release/models/interfaces/openconfig-interfaces.yang',
                            search_path='openconfig/public/release/models:pyang/modules/') }}"
"""

RETURN = """
_raw:
   description: The translated xml string from json
"""

import os
import imp
import re
import sys
import json
import shutil
import uuid


from copy import deepcopy

from ansible.plugins.lookup import LookupBase
from ansible.module_utils.six import StringIO
from ansible.utils.path import unfrackpath, makedirs_safe
from ansible.module_utils._text import to_text
from ansible.errors import AnsibleError

try:
    import pyang
except ImportError:
    raise AnsibleError("pyang is not installed")

try:
    from lxml import etree
except ImportError:
    raise AnsibleError("lxml is not installed")

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display

    display = Display()

JSON2XML_DIR_PATH = "~/.ansible/tmp/json2xml"


class LookupModule(LookupBase):

    def run(self, terms, variables, **kwargs):

        res = []
        try:
            json_config = terms[0]
        except IndexError:
            raise AnsibleError("path to json file must be specified")

        try:
            yang_file = kwargs['yang_file']
        except KeyError:
            raise AnsibleError("value of 'yang_file' must be specified")

        if not os.path.isfile(yang_file):
            raise AnsibleError('%s invalid file path' % yang_file)

        search_path = kwargs.pop('search_path', '')

        for path in search_path.split(':'):
            if path is not '' and not os.path.isdir(path):
                raise AnsibleError('%s is invalid directory path' % path)
        try:
            # validate json
            with open(json_config) as fp:
                json.load(fp)
        except Exception as exc:
            raise AnsibleError("Failed to load json configuration: %s" % (to_text(exc, errors='surrogate_or_strict')))

        root_node = kwargs.get('root', 'config')

        base_pyang_path = sys.modules['pyang'].__file__
        pyang_exec_path = find_file_in_path('pyang')
        pyang_exec = imp.load_source('pyang', pyang_exec_path)

        saved_arg = deepcopy(sys.argv)
        sys.modules['pyang'].__file__ = base_pyang_path

        saved_stdout = sys.stdout
        saved_stderr = sys.stderr
        sys.stdout = sys.stderr = StringIO()

        plugindir = unfrackpath(JSON2XML_DIR_PATH)
        makedirs_safe(plugindir)

        jtox_file_path = os.path.join(JSON2XML_DIR_PATH, '%s.%s' % (str(uuid.uuid4()), 'jtox'))
        xml_file_path = os.path.join(JSON2XML_DIR_PATH, '%s.%s' % (str(uuid.uuid4()), 'xml'))
        jtox_file_path = os.path.realpath(os.path.expanduser(jtox_file_path))
        xml_file_path = os.path.realpath(os.path.expanduser(xml_file_path))

        # fill in the sys args before invoking pyang
        sys.argv = [pyang_exec_path, '-f', 'jtox', '-o', jtox_file_path, yang_file, '-p', search_path, "--lax-quote-checks"]

        try:
            pyang_exec.run()
        except SystemExit:
            pass
        except Exception as e:
            shutil.rmtree(os.path.realpath(os.path.expanduser(JSON2XML_DIR_PATH)), ignore_errors=True)
            raise AnsibleError('Error while generating intermediate (jtox) file: %s' % e)
        finally:
            err = sys.stderr.getvalue()
            if err and 'error' in err.lower():
                shutil.rmtree(os.path.realpath(os.path.expanduser(JSON2XML_DIR_PATH)), ignore_errors=True)
                raise AnsibleError('Error while generating intermediate (jtox) file: %s' % err)

        json2xml_exec_path = find_file_in_path('json2xml')
        json2xml_exec = imp.load_source('json2xml', json2xml_exec_path)

        # fill in the sys args before invoking json2xml
        sys.argv = [json2xml_exec_path, '-t', root_node, '-o', xml_file_path, jtox_file_path, json_config]

        try:
            json2xml_exec.main()
            with open(xml_file_path, 'r+') as fp:
                content = fp.read()

        except SystemExit:
            pass
        finally:
            err = sys.stderr.getvalue()
            if err and 'error' in err.lower():
                shutil.rmtree(os.path.realpath(os.path.expanduser(JSON2XML_DIR_PATH)), ignore_errors=True)
                raise AnsibleError('Error while translating to xml: %s' % err)
            sys.argv = saved_arg
            sys.stdout = saved_stdout
            sys.stderr = saved_stderr

        try:
            content = re.sub(r'<\? ?xml .*\? ?>', '', content)
            root = etree.fromstring(content)
        except Exception as e:
            raise AnsibleError('Error while reading xml document: %s' % e)
        finally:
            shutil.rmtree(os.path.realpath(os.path.expanduser(JSON2XML_DIR_PATH)), ignore_errors=True)
        res.append(etree.tostring(root))

        return res


def find_file_in_path(filename):
    # Check $PATH first, followed by same directory as sys.argv[0]
    paths = os.environ['PATH'].split(os.pathsep) + [os.path.dirname(sys.argv[0])]
    for dirname in paths:
        fullpath = os.path.join(dirname, filename)
        if os.path.isfile(fullpath):
            return fullpath
