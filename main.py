import json
from functools import partial
from re import match
from time import sleep
from typing import Dict, Tuple, List, Optional
from urllib.parse import urlsplit

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
    if any(i.startswith('std::') for i in ids):
        ids = [i.replace('std::', '') for i in ids]
        pass
    else:
        # this page is likely to be another table of content
        print('skip {}'.format(ids))
        return [], None

    header = tree.find(text='Defined in header ')
    if header:
        header = header.parent.find('code').find('a').text.strip('<>')

    return [id_strip(i) for i in ids], header


if __name__ == '__main__':
    s = Session()
    fs = FuturesSession(max_workers=16, session=s)

    header_id_map = {}

    # URL could be duplicated here
    _url_id_map = {}
    for _id, _uri in parse_toc().items():
        if _uri not in _url_id_map:
            _url_id_map[_uri] = set()
        _url_id_map[_uri].add(_id)
    _failed = []
    _success_url_header_map = {}
    for _uri, _ids in _url_id_map.items():
        _resp = None
        while True:
            try:
                _resp = s.get(_uri)
                break
            except RequestException:
                print('retrying {}'.format(_uri))
                sleep(1)
        _detail_ids, _header = get_page(_resp.content)
        if _header is None:
            if _detail_ids:
                _failed.append(_uri)
            continue
        _success_url_header_map[_uri] = _header
        if _header not in header_id_map:
            header_id_map[_header] = set()
        # id from table of content and from detail page
        header_id_map[_header] |= set(_detail_ids) | _ids

    for _failed_uri in _failed:
        for _uri, _header in _success_url_header_map.items():
            if _failed_uri.startswith(_uri):
                # assume these two are in same header
                header_id_map[_header] |= _url_id_map[_failed_uri]

    with open('map.json', 'w') as _failed_uri:
        json.dump({k: list(v) for k, v in header_id_map.items()}, _failed_uri)
