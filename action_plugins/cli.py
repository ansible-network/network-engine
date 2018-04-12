# (c) 2018, Ansible by Red Hat, inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json

from ansible.plugins.action import ActionBase
from ansible.module_utils.connection import Connection, ConnectionError
from ansible.module_utils._text import to_text
from ansible.errors import AnsibleError


class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):
        ''' handler for cli operations '''

        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp  # tmp no longer has any effect

        try:
            command = self._task.args['command']
            parser = self._task.args.get('parser')
            engine = self._task.args.get('engine', 'text_parser')
        except KeyError as exc:
            raise AnsibleError(to_text(exc))

        socket_path = getattr(self._connection, 'socket_path') or task_vars.get('ansible_socket')
        connection = Connection(socket_path)

        try:
            output = connection.get(command)
        except ConnectionError as exc:
            raise AnsibleError(to_text(exc))

        result['stdout'] = output

        # try to convert the cli output to native json
        try:
            json_data = json.loads(output)
        except:
            json_data = None

        result['json'] = json_data

        if parser:
            if engine not in ('text_parser', 'textfsm'):
                raise AnsibleError('missing or invalid value for argument engine')

            new_task = self._task.copy()
            new_task.args = {
                'file': parser,
                'content': (json_data or output)
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

        self._remove_tmp_path(self._connection._shell.tmpdir)

        # this is needed so the strategy plugin can identify the connection as
        # a persistent connection and track it, otherwise the connection will
        # not be closed at the end of the play
        socket_path = getattr(self._connection, 'socket_path') or task_vars.get('ansible_socket')
        self._task.args['_ansible_socket'] = socket_path

        return result
