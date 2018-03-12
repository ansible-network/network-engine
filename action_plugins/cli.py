# (c) 2015, Michael DeHaan <michael.dehaan@gmail.com>
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

import os
import shutil
import tempfile

from ansible import constants as C
from ansible.plugins.action import ActionBase
from ansible.module_utils.connection import Connection, ConnectionError
from ansible.module_utils._text import to_bytes, to_text
from ansible.errors import AnsibleError


class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):

        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)

        try:
            command = self._task.args['command']
            parser = self._task.args.get('parser')
            engine = self._task.args.get('engine', 'text_parser')
        except KeyError as exc:
            raise AnsibleError(to_text(exc))

        socket_path = getattr(self._connection, 'socket_path') or task_vars.get('ansible_socket')
        connection = Connection(socket_path)

        output = connection.get(command)
        result['stdout'] = output

        try:
            json_data = json.loads(output)
        except:
            json_data = None

        result['json'] = json_data

        if parser:
            if engine not in (None, 'text_parser', 'textfsm'):
                raise AnsibleError('missing or invalid value for argument engine')

            new_task = self._task.copy()
            new_task.args = {
                'file': parser,
                'contents': output
            }

            kwargs = {
                'task': new_task,
                'connection': self._connection,
                'play_context': self._play_context,
                'loader': self._loader,
                'templar': self._templar,
                'shared_loader_obj': self._shared_loader_obj
            }

            task_parser = self._shared_loader_obj.action_loader.get(engine, **kwargs)
            result.update(task_parser.run(task_vars=task_vars))

        return result
