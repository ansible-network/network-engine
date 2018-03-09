# (c) 2017, Ansible by Red Hat, inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#
import os
import re
import copy
import json
import collections

from ansible import constants as C
from ansible.plugins.action import ActionBase
from ansible.module_utils.network.common.utils import to_list
from ansible.module_utils.six import iteritems, string_types
from ansible.module_utils._text import to_bytes, to_text
from ansible.errors import AnsibleError, AnsibleUndefinedVariable, AnsibleFileNotFound

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

def warning(msg):
    if C.ACTION_WARNINGS:
        display.warning(msg)


class ActionModule(ActionBase):

    NAMED_PATTERNS = {
        'ALPHAS': '(\w+)',
        'NUMS': '(\d+)',
        'IPV4': '(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])'
    }

    VALID_FILE_EXTENSIONS = ('.yaml', '.yml', '.json')
    VALID_GROUP_DIRECTIVES = ('context', 'block')
    VALID_ACTION_DIRECTIVES = ('pattern_match', 'export_facts', 'lines_template', 'json_template')
    VALID_DIRECTIVES = VALID_GROUP_DIRECTIVES + VALID_ACTION_DIRECTIVES

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)

        try:
            source_dir = self._task.args.get('dir')
            source_file = self._task.args.get('file')
            contents = self._task.args['contents']
        except KeyError as exc:
            return {'failed': True, 'msg': 'missing required argument: %s' % exc}

        if not source_dir and not source_file:
            return {'failed': True, 'msg': 'one of `dir` or `file` must be specified'}
        elif source_dir and source_file:
            return {'failed': True, 'msg': '`dir` and `file` are mutually exclusive arguments'}

        if source_dir:
            sources = self.get_files(to_list(source_dir))
        else:
            sources = to_list(source_file)

        self.facts = {}

        for src in sources:
            if not os.path.exists(src) and not os.path.isfile(src):
                raise AnsibleError("src is either missing or invalid")

            tasks = self._loader.load_from_file(src)

            self.ds = {'contents': contents}
            self.ds.update(task_vars)

            for task in tasks:
                name = task.pop('name', None)

                register = task.pop('register', None)
                export = task.pop('export', False)

                display.vvvv('processing directive: %s' % name)

                when = task.pop('when', None)
                if when is not None:
                    if not self._check_conditional(when, task_vars):
                        warning('skipping task due to conditional check failure')
                        continue

                loop = task.pop('loop', None)

                if loop:
                    loop = self.template(loop, self.ds)
                    res = list()

                    # loop is a hash so break out key and value
                    if isinstance(loop, collections.Mapping):
                        for loop_key, loop_value in iteritems(loop):
                            self.ds['item'] = {'key': loop_key, 'value': loop_value}
                            resp = self._process_directive(task)
                            res.append(resp)

                    # loop is either a list or a string
                    else:
                        for loop_item in loop:
                            self.ds['item'] = loop_item
                            resp = self._process_directive(task)
                            res.append(resp)

                else:
                    res = self._process_directive(task)

                if register:
                    self.ds[register] = res
                    if export:
                        kwargs = {register: res}
                        self.do_export_facts(**kwargs)

            if 'facts' in self.ds:
                self.facts.update(self.ds['facts'])

        result['ansible_facts'] = self.facts
        return result

    def get_files(self, source_dirs):
        include_files = list()
        _processed = set()

        for source_dir in source_dirs:
            if not os.path.isdir(source_dir):
                raise AnsibleError('%s does not appear to be a valid directory' % source_dir)

            for filename in os.listdir(source_dir):
                fn, fext = os.path.splitext(filename)
                if fn not in _processed:
                    _processed.add(fn)

                    filename = os.path.join(source_dir, filename)

                    if not os.path.isfile(filename) or fext not in self.VALID_FILE_EXTENSIONS:
                        continue

                    else:
                        include_files.append(filename)

        return include_files

    def do_block(self, block):

        results = list()
        registers = {}

        for entry in block:
            task = entry.copy()

            name = task.pop('name', None)
            register = task.pop('register', None)

            when = task.pop('when', None)
            if when is not None:
                if not self._check_conditional(when, task_vars):
                    warning('skipping task due to conditional check failure')
                    continue

            loop = task.pop('loop', None)
            if loop:
                loop = self.template(loop, self.ds)

            if 'block' in task:
                res = self.do_block(task['block'])
                if res:
                    results.append(res)
                if register:
                    registers[register] = res

            elif isinstance(loop, collections.Iterable) and not isinstance(loop, string_types):
                loop_result = list()

                for loop_item in loop:
                    self.ds['item'] = loop_item
                    loop_result.append(self._process_directive(task))

                results.append(loop_result)

                if register:
                    registers[register] = loop_result

            else:
                res = self._process_directive(task)
                if res:
                    results.append(res)
                if register:
                    registers[register] = res

        return registers

    def _process_directive(self, task):
        for directive, args in iteritems(task):
            if directive not in self.VALID_DIRECTIVES:
                raise AnsibleError('invalid directive in parser: %s' % directive)
            meth = getattr(self, 'do_%s' % directive)
            if meth:
                if directive in self.VALID_GROUP_DIRECTIVES:
                    return meth(args)
                elif directive in self.VALID_ACTION_DIRECTIVES:
                    return meth(**args)

    def do_export_facts(self, **kwargs):
        if 'facts' not in self.ds:
            self.ds['facts'] = {}
        self.ds['facts'].update(self.template(kwargs, self.ds))

    def _greedy_match(self, contents, start, end=None, match_all=None):
        """ Filter a section of the contents text for matching

        :args contents: The contents to match against
        :args start: The start of the section data
        :args end: The end of the section data
        :args match_all: Whether or not to match all of the instances

        :returns: a list object of all matches
        """
        ds = self.ds if isinstance(self.ds['contents'], string_types) else self.ds['contents']

        contents = self.template(contents, ds)
        section_data = list()

        if match_all:
            while True:
                section_range = self._get_section_range(contents, start, end)
                if not section_range:
                    break

                sidx, eidx = section_range

                if eidx is not None:
                    section_data.append(contents[sidx: eidx])
                    contents = contents[eidx:]
                else:
                    section_data.append(contents[sidx:])
                    break

        else:
            section_data.append(contents)

        return section_data

    def do_pattern_match(self, regex, contents=None, match_all=None, match_until=None, match_greedy=None):
        """ Perform the regular expression match against the contents

        :args regex: The regular expression pattern to use
        :args contents: The contents to run the pattern against
        :args match_all: Specifies if all matches of pattern should be returned
            or just the first occurence

        :returns: list object of matches or None if there where no matches found
        """
        contents = contents or "{{ contents }}"

        if match_greedy:
            return self._greedy_match(contents, regex, end=match_until, match_all=match_all)

        pattern = self.template(regex, self.NAMED_PATTERNS)
        contents = self.template(contents, self.ds)

        if match_all:
            match = self.re_matchall(pattern, contents)
            if match:
                return match
        else:
            match = self.re_search(pattern, contents)
            if match:
                return match

        return None

    def do_json_template(self, template):
        """ Handle the json_template directive

        :args template: the data structure to template

        :return: the templated data
        """
        return self._process_items(template)

    def _process_items(self, template, variables=None):

        templated_items = {}
        variables = variables or self.ds

        for item in template:
            key = self.template(item['key'], variables)

            when = item.get('when')
            if when is not None:
                if not self._check_conditional(when, variables):
                    warning("skipping due to conditional failure")
                    continue

            if 'value' in item:
                value = item.get('value')
                items = None
                item_type = None

            elif 'object' in item:
                items = item.get('object')
                item_type = 'dict'

            elif 'elements' in item:
                items = item.get('elements')
                item_type = 'list'

            when = item.get('when')

            loop = item.get('repeat_for')
            loop_data = self.template(loop, variables) if loop else None
            loop_var = item.get('repeat_var', 'item')

            if items:
                if loop:
                    if isinstance(loop_data, collections.Iterable) and not isinstance(loop_data, string_types):
                        templated_value = list()

                        for loop_item in loop_data:
                            variables[loop_var] = loop_item
                            templated_value.append(self._process_items(items, variables))

                        if item_type == 'list':
                            templated_items[key] = templated_value

                        elif item_type == 'dict':
                            if key not in templated_items:
                                templated_items[key] = {}

                            for t in templated_value:
                                templated_items[key].update(t)
                    else:
                        templated_items[key] = []

                else:
                    val = self._process_items(items, variables)

                    if item_type == 'list':
                        templated_value = [val]
                    else:
                        templated_value = val

                    templated_items[key] = templated_value

            else:
                templated_value = self.template(value, variables)
                templated_items[key] = templated_value

        return templated_items

    def _get_section_range(self, contents, start, end=None):

        try:
            context_start_re = re.compile(start, re.M)
            if end:
                context_end_re = re.compile(end, re.M)
                include_end = True
            else:
                context_end_re = context_start_re
                include_end = False
        except KeyError as exc:
            raise AnsibleError('Missing required key %s' % to_text(exc))

        context_start = re.search(context_start_re, contents)
        if not context_start:
            return

        string_start = context_start.start()
        end = context_start.end() + 1

        context_end = re.search(context_end_re, contents[end:])
        if not context_end:
            return (string_start, None)

        if include_end:
            string_end = end + context_end.end()
        else:
            string_end = end + context_end.start()

        return (string_start, string_end)

    def _get_context_data(self, entry, contents):
        name = entry['name']

        context = entry.get('context', {})
        context_data = list()

        if context:
            while True:
                context_range = self._get_context_range(name, context, contents)

                if not context_range:
                    break

                start, end = context_range

                if end is not None:
                    context_data.append(contents[start: end])
                    contents = contents[end:]
                else:
                    context_data.append(contents[start:])
                    break

        else:
            context_data.append(contents)

        return context_data

    def _get_context_matches(self, entry, context_data):
        matches = list()

        for data in context_data:
            variables = {'matches': list()}

            for match in entry['matches']:
                when = entry.get('when')

                if when is not None:
                    if not self._check_conditional(when, variables):
                        warning('skipping match statement due to conditional check')
                        continue

                pattern = self.template(match['pattern'], self.NAMED_PATTERNS)
                match_var = match.get('match_var')
                match_all = match.get('match_all')

                if match_all:
                    res = re.findall(pattern, data, re.M)
                else:
                    match = re.search(pattern, data, re.M)
                    if match:
                        res = list(match.groups())
                    else:
                        res = None

                if match_var:
                    variables[match_var] = res

                variables['matches'].append(res)

            matches.append(variables)
        return matches

    def template(self, data, variables, convert_bare=False):

        if isinstance(data, collections.Mapping):
            templated_data = {}
            for key, value in iteritems(data):
                templated_key = self.template(key, variables, convert_bare=convert_bare)
                templated_data[templated_key] = self.template(value, variables, convert_bare=convert_bare)
            return templated_data

        elif isinstance(data, collections.Iterable) and not isinstance(data, string_types):
            return [self.template(i, variables, convert_bare=convert_bare) for i in data]

        else:
            data = data or {}
            tmp_avail_vars = self._templar._available_variables
            self._templar.set_available_variables(variables)
            try:
                resp = self._templar.template(data, convert_bare=convert_bare)
                resp = self._coerce_to_native(resp)
            except AnsibleUndefinedVariable:
                resp = None
                pass
            finally:
                self._templar.set_available_variables(tmp_avail_vars)
            return resp

    def _coerce_to_native(self, value):
        if not isinstance(value, bool):
            try:
                value = int(value)
            except Exception as exc:
                if value is None or len(value) == 0:
                    return None
                pass
        return value

    def _check_conditional(self, when, variables):
        conditional = "{%% if %s %%}True{%% else %%}False{%% endif %%}"
        return self.template(conditional % when, variables)

    def re_search(self, regex, value):
        obj = {}
        regex = re.compile(regex, re.M)
        match = regex.search(value)
        if match:
            items = list(match.groups())
            if regex.groupindex:
                for name, index in iteritems(regex.groupindex):
                    obj[name] = items[index - 1]
            obj['matches'] = items
        return obj or None

    def re_matchall(self, regex, value):
        #import epdb; epdb.serve()
        objects = list()
        regex = re.compile(regex)
        for match in re.findall(regex.pattern, value, re.M):
            obj = {}
            obj['matches'] = match
            if regex.groupindex:
                for name, index in iteritems(regex.groupindex):
                    if len(regex.groupindex) == 1:
                        obj[name] = match
                    else:
                        obj[name] = match[index - 1]
            objects.append(obj)
        return objects
