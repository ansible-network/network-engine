# (c) 2018, Ansible by Red Hat, inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#
from itertools import chain

from ansible.module_utils.six import iteritems
from ansible.module_utils.network.common.utils import sort_list

from ansible.module_utils._text import to_native
from ansible.module_utils.six import string_types, binary_type, text_type
from ansible.module_utils.parsing.convert_bool import boolean


def dict_merge(base, other):
    """ Return a new dict object that combines base and other

    This will create a new dict object that is a combination of the key/value
    pairs from base and other.  When both keys exist, the value will be
    selected from other.  If the value is a list object, the two lists will
    be combined and duplicate entries removed.

    :param base: dict object to serve as base
    :param other: dict object to combine with base

    :returns: new combined dict object
    """
    if not isinstance(base, dict):
        raise AssertionError("`base` must be of type <dict>")
    if not isinstance(other, dict):
        raise AssertionError("`other` must be of type <dict>")

    combined = dict()

    for key, value in iteritems(base):
        if isinstance(value, dict):
            if key in other:
                item = other.get(key)
                if item is not None:
                    if isinstance(other[key], dict):
                        combined[key] = dict_merge(value, other[key])
                    else:
                        combined[key] = other[key]
                else:
                    combined[key] = item
            else:
                combined[key] = value
        elif isinstance(value, list):
            if key in other:
                item = other.get(key)
                if item is not None:
                    try:
                        combined[key] = list(set(chain(value, item)))
                    except TypeError:
                        value.extend([i for i in item if i not in value])
                        combined[key] = value
                else:
                    combined[key] = item
            else:
                combined[key] = value
        else:
            if key in other:
                other_value = other.get(key)
                if other_value is not None:
                    if sort_list(base[key]) != sort_list(other_value):
                        combined[key] = other_value
                    else:
                        combined[key] = value
                else:
                    combined[key] = other_value
            else:
                combined[key] = value

    for key in set(other.keys()).difference(base.keys()):
        combined[key] = other.get(key)

    return combined


def _handle_type_str(value):
    if isinstance(value, string_types):
        return value
    return str(value)


def _handle_type_bool(value):
    if isinstance(value, bool) or value is None:
        return value

    if isinstance(value, string_types) or isinstance(value, int):
        try:
            return boolean(value)
        except TypeError as e:
            raise TypeError('%s cannot be converted to a bool' % type(value))


def _handle_type_int(value):
    if isinstance(value, int):
        return value

    if isinstance(value, string_types):
        return int(value)

    raise TypeError('%s cannot be converted to an int' % type(value))


def _handle_type_float(value):
    if isinstance(value, float):
        return value

    if isinstance(value, (binary_type, text_type, int)):
        return float(value)

    raise TypeError('%s cannot be converted to a float' % type(value))


def handle_type(value, want):
    type_checker = {
        'str': _handle_type_str,
        'bool': _handle_type_bool,
        'int': _handle_type_int,
        'float': _handle_type_float,
    }.get(want)

    try:
        return type_checker(value)
    except (TypeError, ValueError) as e:
        raise AssertionError("Value %s is of type %s and we were unable to convert to %s: %s" %
                             (value, type(value), want, to_native(e)))
