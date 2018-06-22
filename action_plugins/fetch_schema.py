# (c) 2017, Ansible by Red Hat, inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#
from __future__ import absolute_import
import os
import re
import copy
import json
import collections
import yaml
import sys
import q

from ansible import constants as C
from ansible.plugins.action import ActionBase
from ansible.module_utils.network.common.utils import to_list
from ansible.module_utils.six import iteritems, string_types
from ansible.module_utils._text import to_bytes, to_text
from ansible.module_utils.connection import Connection, ConnectionError
from ansible.utils.path import unfrackpath, makedirs_safe
from ansible.errors import AnsibleError, AnsibleUndefinedVariable, AnsibleFileNotFound

from ansible.module_utils.six.moves.urllib.parse import urlsplit
from collections import OrderedDict


try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()
try:
    from lxml import etree
    HAS_XML = True
except ImportError:
    HAS_XML = False

try:
    from lxml.etree import tostring
except ImportError:
    from xml.etree.ElementTree import tostring

try:
    import jxmlease
    HAS_JXMLEASE = True
except ImportError:
    HAS_JXMLEASE = False

def warning(msg):
    if C.ACTION_WARNINGS:
        display.warning(msg)

class SchemaStore(object):
    def __init__(self, conn, folder):
        self._conn = conn
        self._schema_cache = []
        self._all_schema_list = None
        self._folder = folder

    def get_schema_description(self):
        content = '''
          <filter>
            <netconf-state xmlns="urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring">
              <schemas>
                <schema>
                    <identifier/>
                </schema>
              </schemas>
            </netconf-state>
          </filter>
        '''
        xml_request = '<%s>%s</%s>' %('get', content, 'get')
        try:
          response = self._conn.dispatch(xml_request)
        except ConnectionError as e:
          raise ValueError(to_text(e))
        response = to_bytes(response, errors='surrogate_or_strict')
        tree = etree.ElementTree(etree.fromstring(response))
        tree_root = tree.getroot()
        res_str = etree.tostring(tree_root, pretty_print=True)

        if not HAS_JXMLEASE:
            raise ValueError('jxmlease is required to store response in json format'
                             'but does not appear to be installed. '
                             'It can be installed using `pip install jxmlease`')
        res_json = jxmlease.parse(res_str)
        self._all_schema_list = res_json["data"]["netconf-state"]["schemas"]["schema"]
        return

    def get_one_schema(self, schema_id):
        if self._all_schema_list == None:
	    self.get_schema_description()
        
        found = False
        # Search for schema that are supported by device.
        # Also get namespace for retreival
        schema_cache_entry = {}
        for index, schema_list in enumerate(self._all_schema_list):
            if to_bytes(schema_id) == to_bytes(schema_list["identifier"],
                                            errors='surrogate_or_strict'):
                schema_cache_entry["id"] = schema_id
                schema_cache_entry["ns"] = self._all_schema_list[index]["namespace"]
                schema_cache_entry["format"] = self._all_schema_list[index]["format"]
                found = True
                break

        if found:
            content = ("<identifier> %s </identifier>" % (schema_cache_entry["id"]))
            xmlns = "urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring"
            xml_request = '<%s xmlns="%s"> %s </%s>' %('get-schema',
                                        xmlns, content, 'get-schema')
            try:
                response = self._conn.dispatch(xml_request)
            except ConnectionError as e:
                raise ValueError(to_text(e))
            response = to_bytes(response, errors='surrogate_or_strict')
            tree = etree.ElementTree(etree.fromstring(response))
            tree_root = tree.getroot()
            res_str = etree.tostring(tree_root, pretty_print=True)

            if not HAS_JXMLEASE:
                raise ValueError('jxmlease is required to store response in json format'
                                 'but does not appear to be installed. '
                                 'It can be installed using `pip install jxmlease`')
            res_json = jxmlease.parse(res_str)
            data_model = res_json["rpc-reply"]["data"]
            yang_file_name = schema_id + '.yang'
            abs_file_name = os.path.join(self._folder, yang_file_name)
            with open(abs_file_name, 'w') as f:
                f.write(data_model)
            self._schema_cache.append(schema_cache_entry)

        q(self._schema_cache, found, data_model)
        return (found, data_model)

    def check_schema_exist(self, schema_id):
        found = False
        for schema_cache_entry in self._schema_cache:
            if schema_id == schema_cache_entry["id"]:
                found = True
                break
        return found
          


class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)

        try:
           schemas = self._task.args.get('schema')
        except ValueError as exc:
           return dict(failed=True, msg="schema: mandatory agrgument")

        #Optional Arguments Handling
        dest_folder = self._task.args.get('destination')
        if dest_folder == None:
            dest_folder = self._get_default_folder()

        socket_path = self._connection.socket_path
        conn = Connection(socket_path)

        ss = SchemaStore(conn, dest_folder)

        try:
           for schema in schemas:
              ss.get_one_schema(schema)
        except ValueError as exc:
           return dict(failed=True, msg=to_text(exc))
        
        result["changed"] = True
        return result

    def _get_working_path(self):
        cwd = self._loader.get_basedir()
        if self._task._role is not None:
            cwd = self._task._role._role_path
        return cwd

    def _get_default_folder(self):
        cwd = self._get_working_path()
        default_folder = cwd + '/yang_schemas'
        makedirs_safe(default_folder)
        return default_folder

