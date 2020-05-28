import json
from functools import partial
from re import match
from time import sleep
from typing import Dict, Tuple, List, Optional

from bs4 import BeautifulSoup, Tag
from requests import Session, Response, RequestException
from requests_futures.sessions import FuturesSession

domain = 'https://en.cppreference.com'

assemble_url = lambda path: '{}{}'.format(domain, path)
toc = assemble_url('/w/cpp/symbol_index')

BeautifulSoup = partial(BeautifulSoup, features="html.parser")

s: Session
fs: FuturesSession

ID_REGEX = r'[_a-zA-Z][_a-zA-Z0-9]*'


def id_strip(_id: str):
    _m = match(ID_REGEX, _id)
    assert _m, _id
    return _m.group()


def parse_toc() -> Dict[str, str]:
    """
    simply returns identifiers, ignore same ids in different header
    return {id: link}
    """
    toc_tree = BeautifulSoup(s.get(toc).content)

    root, *_ = toc_tree.select('div#mw-content-text')
    assert root is not None

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

    # todo: handle same name in different header
    res = {id_strip(a.find('tt').text.strip('()<>')): assemble_url(a.attrs['href'])
           for a in root.find_all(a_with_link_and_text)}
    return res


def get_page(cont: bytes) -> Tuple[List[str], Optional[str]]:
    """
    return list of identifiers and the header
    """
    tree = BeautifulSoup(cont)

    heading = tree.find('h1', 'firstHeading')
    ids = [i.strip() for i in heading.text.split(',')]
    if all(i.startswith('std::') for i in ids):
        # everything's fine
        pass
    else:
        # this page is likely to be another table of content
        print('skip {}'.format(ids))
        return [], None

    header = tree.find(text='Defined in header ')
    if header:
        header = header.parent.find('code').find('a').text.strip('<>')

    return [id_strip(i[5:]) for i in ids], header


if __name__ == '__main__':
    s = Session()
    fs = FuturesSession(max_workers=16, session=s)

    header_id_map = {}

    # URL could be duplicated here
    for _uri in set(parse_toc().values()):
        _resp = None
        while True:
            try:
                _resp = s.get(_uri)
                break
            except RequestException:
                print('retrying {}'.format(_uri))
                sleep(1)
        _ids, _header = get_page(_resp.content)
        if _header is None:
            print('no header for {} in {}'.format(_ids, _uri))
            continue
        if _header not in header_id_map:
            header_id_map[_header] = []
        header_id_map[_header] += _ids

    with open('map.json', 'w') as _f:
        json.dump(header_id_map, _f, indent=2)
