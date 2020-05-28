from typing import Dict, List, Set

from bs4 import BeautifulSoup, Tag
from requests import Session
from requests_futures.sessions import FuturesSession

toc = 'https://en.cppreference.com/w/cpp/symbol_index'

s: Session
fs: FuturesSession


def parse_toc() -> Set[str]:
    """
    simply returns identifiers in a set
    """
    toc_tree = BeautifulSoup(s.get(toc).content, features="html.parser")

    _root, *_ = toc_tree.select('div#mw-content-text')
    assert _root is not None

    def a_with_link_and_text(tag: Tag):
        return (
                tag.name == 'a' and
                tag.has_attr('href') and
                tag.has_attr('title') and
                (
                        tag.attrs['href'][3:].replace('_', ' ') == tag.attrs['title']
                ) and
                any(c.name == 'tt' for c in tag.children)
        )

    _res = {a.find('tt').text.strip('()<>') for a in _root.find_all(a_with_link_and_text)}
    return _res


if __name__ == '__main__':
    s = Session()
    fs = FuturesSession(max_workers=16, session=s)

    parse_toc()
