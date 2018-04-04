# (c) 2018, Ansible by Red Hat, inc
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#
import re

from ansible.module_utils.six import iteritems


def get_value(m, i):
    return m.group(i) if m else None


class ParserEngine(object):

    def __init__(self, text):
        self.text = text

    def match(self, regex, match_all=None, match_until=None, match_greedy=None):
        """ Perform the regular expression match against the contents

        :args regex: The regular expression pattern to use
        :args contents: The contents to run the pattern against
        :args match_all: Specifies if all matches of pattern should be returned
            or just the first occurence

        :returns: list object of matches or None if there where no matches found
        """
        contents = self.text

        if match_greedy:
            return self._match_greedy(contents, regex, end=match_until, match_all=match_all)
        elif match_all:
            return self._match_all(contents, regex)
        else:
            return self._match(contents, regex)

    def _match_all(self, contents, pattern):
        match = self.re_matchall(pattern, contents)
        if match:
            return match

    def _match(self, contents, pattern):
        match = self.re_search(pattern, contents)
        return match

    def _match_greedy(self, contents, start, end=None, match_all=None):
        """ Filter a section of the contents text for matching

        :args contents: The contents to match against
        :args start: The start of the section data
        :args end: The end of the section data
        :args match_all: Whether or not to match all of the instances

        :returns: a list object of all matches
        """
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

    def _get_section_range(self, contents, start, end=None):

        context_start_re = re.compile(start, re.M)
        if end:
            context_end_re = re.compile(end, re.M)
            include_end = True
        else:
            context_end_re = context_start_re
            include_end = False

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

    def re_search(self, regex, value):
        obj = {'matches': []}
        regex = re.compile(regex, re.M)
        match = regex.search(value)
        if match:
            items = list(match.groups())
            if regex.groupindex:
                for name, index in iteritems(regex.groupindex):
                    obj[name] = items[index - 1]
            obj['matches'] = items
        return obj

    def re_matchall(self, regex, value):
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
