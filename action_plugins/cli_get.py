# -*- coding: utf-8 -*-

# (c) 2018, Ansible by Red Hat, inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
#
# You should have received a copy of the GNU General Public License
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
#
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

from ansible.plugins.action.normal import ActionModule as ActionBase
from ansible.errors import AnsibleError


class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = dict()

        if self._play_context.connection != 'network_cli':
            raise AnsibleError('cli_get requires connection=network_cli')

        result = super(ActionModule, self).run(tmp, task_vars)

        return result
