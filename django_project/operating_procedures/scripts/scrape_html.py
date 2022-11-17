# scrape_html.py

from itertools import chain
import re

import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from django.db import transaction

from operating_procedures import models


casetext_domain = "casetext.com"
casetext = f"https://{casetext_domain}/"
casetext_61B = casetext + \
                 "regulation/florida-administrative-code/" \
                 "department-61-department-of-business-and-professional-regulation/" \
                 "division-61b-division-of-florida-condominiums-timeshares-and-mobile-homes/"

fl_leg_domain = "leg.state.fl.us"
fl_legislature = f"http://www.{fl_leg_domain}/"
chapter_719 = fl_legislature + \
                "statutes/index.cfm?App_mode=Display_Statute&URL=0700-0799/0719/0719.html"

emsp = '\u2003'

class HTTP_error(Exception):
    pass

class Find_error(Exception):
    pass

Dump_body = False
Max_title = 50


def find1(soup, name, attrs={}, recursive=False, string=None, error_if_none=True, **kwargs):
    all = soup.find_all(name, attrs, recursive, string, **kwargs)
    if not all and not error_if_none:
        return None
    if len(all) != 1:
        raise Find_error(f"{soup.name}: Expected one {name=} {attrs=}, got {len(all)}")
    return all[0]

def get(url):
    r'''Gets url and returns the soup!

    Checks status_code in response, and Content-Type == 'text/html'.

    Also corrects encoding, if the encoding in Content-Type or meta charset differ.
    '''
    response = requests.get(url)
    if response.status_code != 200:
        raise HTTP_error(f"{url=}: status_code {response.status_code}")
    encoding = response.encoding
    where = 'from response'
    content_type = response.headers['Content-Type'].split(';')
    #print(url, "encoding:", encoding, "content-type:", content_type)
    if content_type[0] != 'text/html':
        raise HTTP_error(f"Got Content-Type {response.headers['Content-Type']}")
    if len(content_type) == 2:
        arg = content_type[1].lstrip()
        assert arg.startswith('charset='), f"expected 'charset', got {arg}"
        e2 = arg[8:]
        if e2 != encoding:
            print(f"response.encoding is {encoding}, got charset {e2} in Content-Type, "
                  "changing encoding")
            encoding = e2
            response.encoding = encoding
            where = 'from Content-Type'
    soup = BeautifulSoup(response.text, 'html.parser')
    m = soup.head.find('meta', charset=True)
    if m is not None:
        if m['charset'] != encoding:
            print(f"meta charset is {encoding}, got encoding {e2} {where}, "
                  "changing encoding")
            encoding = m['charset']
            response.encoding = encoding
            soup = BeautifulSoup(response.text, 'html.parser')
    #print(f"{soup.head.find('meta')}")
    return soup

def scrape_61B(trace=False):
    r'''Expectes a list of chapters.  Passes all 75-79 chapters to process_61B_chapter.
    '''
    global item_order
    item_order = 1
    soup = get(casetext_61B)
    #article = find1(soup.body, 'article', recursive=True)
    article = soup.body.article
    ul = find1(article, 'ul', recursive=False)
    #print(f"scrape_61B got ul with {len(ul.contents)} elements")
    chapters_seen = []
    for li in ul.children:
        a = li.a
        title = find1(a, 'span', recursive=True, class_='title').string
        assert title.startswith('Chapter 61B-')
        ch_number = int(title[12:].split()[0])
        #print(f"scrape_61B got li.a tag {a.contents[-1]=}, {ch_number=}")
        if 75 <= ch_number <= 79:
            if 'Repealed' not in title:
                assert not chapters_seen or ch_number == chapters_seen[-1] + 1
                chapters_seen.append(ch_number)
                href = a['href']
                if href[0] != '/':
                    href = casetext + href
                process_61B_chapter(ch_number, title, href)
    assert chapters_seen and chapters_seen[-1] == 79


def process_61B_chapter(ch_number, title, url):
    r'''E.g., 61B-75
    '''
    title = title[title.index(' - ') + 3: title.index('(\u00a7') - 1]  # \u00a7 is section sign
    #print(f"process_61B_chapter got {ch_number=}, {title=}, url=...{url[-30:]}")
    soup = get(url)
    #article = find1(soup.body, 'article', recursive=True)
    article = soup.body.article
    ul = find1(article, 'ul', recursive=False)
    chapter_item = create_item(f"61B-{ch_number}", ch_number, title)
    for body_order, li in enumerate(ul.children, 1):
        a = li.a
        href = a['href']
        if href[0] != '/':
            href = casetext + href
        process_61B_section(chapter_item, body_order, href)
    set_num_elements(chapter_item, body_order)


def create_item(citation, number, title, parent=None, body_order=None):
    global item_order
    item = models.Item(version=version_obj, citation=citation, number=number,
                       parent=parent, item_order=item_order, body_order=body_order,
                       num_elements=0, has_title=bool(title))
    item.save()
    item_order += 1
    if title:
        create_paragraph(title, 0, item)
    return item


def set_num_elements(item, num_elements):
    if num_elements > 0:
        item.num_elements = num_elements
        item.save()


def process_61B_section(parent, body_order, url):
    r'''E.g., 61B-75.008
    '''
    soup = get(url)
    #print(f"process_61B_section {parent.citation=}, {body_order=}")
    article = find1(soup.body, 'article', recursive=True)
    body = find1(article, 'div', class_="content-body", recursive=True)
    title = body.find('section', class_="codified-law-title").string
    if title.startswith('Section '):
        title = title[8: ]
    i = title.index(' - ')
    citation = title[: i] + ' '
    title = title[i + 3:]
    number = citation[citation.index('.'):]  # e.g., '.008 '
    #print(f"found section title {citation=}, {number=}, {title=}")

    section_item = create_item(citation, number, title, parent, body_order)

    container = body.find('section', class_='act', recursive=True).section

    #print(f"process_61B_section {section_item.citation}:")
    body_order = 0
    for child in container.children:
        if isinstance(child, NavigableString):
            #print(f"  process_61B_section {section_item.citation} got text child, "
            #      f"len {len(str(child))}")
            body_order += 1
            create_paragraph(str(child), body_order, section_item)
        elif child.name == 'p':
            #print(f"  process_61B_section {section_item.citation} got 'p' child") 
            body_order += process_p_tag(section_item, body_order, child)
        elif child.name == 'section':
            if 'class' in child.attrs:
                if 'citeAs' in child['class']:
                    #print(f"  process_61B_section {citation} got 'citeAs' child "
                    #      f"{child.prettify()}")
                    body_order += process_citeAs(section_item, body_order, child)
                elif 'historicalNote' in child['class']:
                    #print(f"  process_61B_section {citation} got 'historicalNote' child "
                    #      f"{child.prettify()}")
                    body_order += process_historicalNote(section_item, body_order, child)
                else:
                    print(f"  process_61B_section {citation} got unknown child attrs "
                          f"{child.name=} {child['class']} -- IGNORED")
            else:
                #print(f"  process_61B_section {section_item.citation} got normal child") 
                body_order += 1
                process_61B_paragraph(section_item, child, body_order)
        else:
            print(f"  process_61B_section {citation} got unknown child name {child.name=} "
                   "-- IGNORED")
    #print(f"process_61B_section {section_item.citation} got num_element={body_order}")
    set_num_elements(section_item, body_order)


def process_citeAs(item, body_order, tag):
    text = get_string(tag, allow_p=True).strip()
    body_order += 1
    #print(f"process_citeAs {item.citation} {body_order=} {text=!r}")
    assert text, f"process_citeAs {item.citation} {body_order=} {text=!r} tag={tag.prettify()}"
    create_note(item, body_order, text, type='citeAs')
    return 1


def process_historicalNote(item, body_order, tag):
    if len(tag.contents) == 1 and isinstance(tag.contents[0], NavigableString):
        # History note
        text = 'History. ' + str(tag.contents[0])
        body_order += 1
        #print(f"process_historicalNote {item.citation}, {body_order=} 1 str child {text=!r}")
        create_note(item, body_order, text, prefix_len=7)
        return 1
    text = get_string(tag, allow_p=True).strip()
    text2 = re.sub(r'  *', ' ', text)                  # convert 2 or more spaces to 1 space
    text2 = re.sub(r'\) *([(0-9,])', r')\1', text2)    # delete spaces between ) and (, number or ,
    text2 = re.sub(r'([0-9]) *([,(])', r'\1\2', text2) # delete spaces between number and , or (

    # Make sure there's exactly 1 space between 'law' and 'implemented'.
    text2 = re.sub(r'(law) *(implemented)', r'\1 \2', text2, flags=re.IGNORECASE)

    # Make sure there's exactly 1 space between 'specific' or 'rulemaking' and 'authority'.
    text2 = re.sub(r'(specific|rulemaking) *(authority)', r'\1 \2', text2, flags=re.IGNORECASE)

    authority = re.search(r'(specific|rulemaking) *authority\.?', text2, flags=re.IGNORECASE)
    law_implemented = re.search(r'law *implemented\.?', text2, flags=re.IGNORECASE)
    if authority:
        body_order += 1
        #print(f"process_historicalNote {item.citation}, {body_order=} authority:")
        #print(f"  {text=!r}")
        #print(f"  {text2=!r}")
        assert authority.start() == 0
        if law_implemented:
            a_text = text2[0: law_implemented.start() - 1].rstrip()
            create_note(item, body_order, a_text, prefix_len=authority.end())
            l_text = text2[law_implemented.start():]
            create_note(item, body_order + 1, l_text,
                        prefix_len=law_implemented.end() - law_implemented.start())
            #print(f"  and law impl {a_text=!r}")
            #print(f"      {l_text=!r}")
            return 2
        #print(f"  {text2=!r}")
        create_note(item, body_order, text2, prefix_len=authority.end())
        return 1
    if law_implemented:
        body_order += 1
        #print(f"process_historicalNote {item.citation}, {body_order=} law impl {text2=!r}")
        assert law_implemented.start() == 0
        create_note(item, body_order, text2, prefix_len=15)
        return 1
    print(f"process_historicalNote {item.citation}, {body_order=} NADA {text=!r} {text2=!r} "
          f"-- IGNORED")
    return 0


def process_p_tag(item, body_order, p_tag):
    r'''Returns amount to increment body_order by.
    '''
    saw_text = False
    inc = 0
    for i, p_child in enumerate(p_tag.children, 1):
        if not isinstance(p_child, NavigableString):
            if p_child.name == 'table':
                inc += 1
                process_table(item, p_child, body_order + inc)
            else:
                print(f"  process_p_tag: while examining {p_tag.prettify()},")
                print(f"  process_p_tag {item.citation} NOTICE: 'p' with {p_child.name=} "
                      f"as {i} child -- IGNORED")
        elif saw_text:
            print(f"  process_p_tag: while examining {p_tag.prettify()},")
            print(f"  process_p_tag {item.citation} NOTICE: multiple NavigableStrings -- IGNORED")
        else:
            inc += 1
            create_paragraph(str(p_child), body_order + inc, item)
            saw_text = True
    return inc


def process_61B_paragraph(parent_item, container, body_order):
    r'''Creates a new Item and assocated Paragraphs.

    Doesn't return anything.
    '''
    bulletid = container.contents[0]
    #print(f"process_61B_paragraph {parent_item.citation}, first child is {bulletid.name=} "
    #      f"{tuple(bulletid.attrs.keys())=}")
    assert bulletid.name == 'span' and 'data-bulletid' in bulletid.attrs, \
           f"process_61B_paragraph {parent_item.citation} " \
           f"expected 'data-bulletid' 'span', " \
           f"got {bulletid.name=}, {tuple(bulletid.attrs.keys())=}"
    number = get_string(bulletid)
    citation = parent_item.citation + number
    text = container.contents[1]
    title = None
    i = -1
    start = 0
    if isinstance(text, NavigableString):
        while True:
            i = str(text).find('. ', i + 1)
            if 0 < i <= Max_title:
                title = str(text)[:i + 1].strip()
                rest = str(text)[i + 1:].lstrip()
                if rest:
                    if rest[0].isupper() or \
                       rest[0] in '"\u201c\u201f\u201d\u301d\u301e' and rest[1].isupper():
                        #print(f"{citation=}: '{title=}'")
                        start = 1
                        break
                elif len(container.contents) > 1:
                    #print(f"{citation=}: no body, '{title=}'")
                    start = 1
                    break
            else:
                #if i < 0:
                #    print(f"{citation=}: no title, no '.' found in '{str(text)[:70]}'")
                #else:
                #    print(f"{citation=}: no title, sentence too long in "
                #          f"'{str(text)[:min(i + 1, 70)]}'")
                title = None
                rest = str(text).strip()
                start = 1
                break

    #print(f"process_61B_paragraph {citation=}, {number=}, {title=}:")
    item = create_item(citation, number, title, parent_item, body_order)
    child_body_order = 0
    text = ''
    post_fns = []
    child_body_order = 0

    def check_text(dec=1):
        nonlocal text, post_fns, child_body_order
        if text:
            child_body_order += 1
            para = create_paragraph(text, child_body_order, item)
            for post_fn in post_fns:
                post_fn(para)
            text = ''
            post_fns = []

    for child in container.contents[1:]:
        if isinstance(child, NavigableString):
            if child_body_order == 0 and title is not None:
                text = text_cat(text, rest)
            else:
                text = text_cat(text, str(child))
            #print(f"  process_61B_paragraph {citation} got text child {len(text)=}")
        elif child.name == 'p':
            check_text()
            #print(f"  process_61B_paragraph {citation} got 'p' {child.attrs=}")
            child_body_order += process_p_tag(item, child_body_order, child)
        elif child.name == 'span':
            text = text_cat(text, process_61B_span(child, citation))
        elif child.name == 'a':
            #print(f"  process_61B_paragraph {citation} got 'a' {child.attrs=}")
            a_text, post_fn = process_61B_a(child, len(text), citation)
            text = text_cat(text, a_text)
            post_fns.append(post_fn)
        elif child.name == 'section':
            check_text()
            #print(f"  process_61B_paragraph {citation} got 'section' child") 
            if child.attrs:
                print(f"  process_61B_paragraph {citation} WARNING got unexpected attrs in "
                      f"section {child.attrs=}")
            child_body_order += 1
            process_61B_paragraph(item, child, child_body_order)
        else:
            print(f"  process_61B_paragraph {citation} got unknown child name {child.name=} "
                  f"{child.attrs=}, IGNORED")
    check_text(0)
    #print(f"process_61B_paragraph {citation} setting num_elements={child_body_order}")
    set_num_elements(item, child_body_order)


def text_cat(a, b):
    b = b.strip()
    if not a:
        return b
    if not b:
        return a
    return ' '.join((a, b))


def process_61B_span(span, citation):
    ans = ''
    for i, child in enumerate(span.children, 1):
        if isinstance(child, NavigableString):
            ans = text_cat(ans, str(child))
        else:
            print(f"process_61B_span {citation} WARNING: child {i}, {child.prettify()}, IGNORED")
    #print(f"process_61B_span {citation} got 'span' {span.attrs=}, returning '{ans}'")
    return ans


def process_61B_a(a, char_offset, citation):
    ans = ''
    for i, child in enumerate(a.children, 1):
        if isinstance(child, NavigableString):
            ans = text_cat(ans, str(child))
        else:
            print(f"process_61B_a {citation} WARNING: child {i}, {child.prettify()}, IGNORED")
    def create_annotation(para):
        models.Annotation(paragraph=para, type='link', char_offset=char_offset, length=len(ans),
                          info=a['href']).save()
    return ans, create_annotation


s_cite_re = re.compile(r"""
            # Citations are "s. 719.106"

            # s. Prefix:
            \bs\.\ *

            # Capture all citation reference as a group
            (
              # cite:
              (?: [0-9]+[A-Z][0-9]*-[0-9]+            # 61B-75 or 61H1-20
                | [0-9]{2,}                           # or 719
              )
              (?:\.[0-9]+                             # optional: .106
                 (?: (?:\ *\([0-9a-z]+\))+            #   optional: one or more "(xx)"
                     (?:\ *[0-9a-z]+\.)*              #             any number of "xx."
                 )?
              )?
            ) # end of citation
          """,
          re.VERBOSE | re.IGNORECASE)

ss_cite_re = re.compile(r"""
            # Citations are "s. 719.106" or "section 719.106" or "subsection 61B-75.004"
            # or "ss. 719.106, 719.107 and 719.109"
            # or "ss. 719.106-719.108"

            # Optional Prefix:
            (?:(?:\bss\.|\bsections?|\bsubsections?|\bparagraphs?|\bsubparagraphs?
                 |\brules?|\bchapters?)\ *)

            # Capture all citation references as a group
            (
              # first cite:
              (?: [0-9]+[A-Z][0-9]*-[0-9]+            # 61B-75 or 61H1-20
                | [0-9]{2,}                           # or 719
              )
              (?:\.[0-9]+                             # optional: .106
                 (?: (?:\ *\([0-9a-z]+\))+            #   optional: one or more "(xx)"
                     (?:\ *[0-9a-z]+\.)*              #             any number of "xx."
                 )?
              )?

              # optionally hyphenated...
              (?: \ *-\ *                             # hyphen for range of cites
                  # last cite (.section required here to avoid confusion with "3."):
                  (?: [0-9]+[A-Z][0-9]*-[0-9]+
                    | [0-9]{2,}
                  )
                  (?: \.[0-9]+
                      (?: (?:\ *\([0-9a-z]+\))+
                          (?:\ *[0-9a-z]+\.)*
                      )?
                  )?
              )?

              # any number of "," and/or "and" seperated list of cites
              (?:
                (?: (?: , (?: \ *and)? \ *)           # , and? 
                  | (?: \ *and\ *))                   # and without ,

                # first cite (.section required here to avoid confusion with "3."):
                (?: [0-9]+[A-Z][0-9]*-[0-9]+
                  | [0-9]{2,}
                )
                (?: \.[0-9]+
                    (?: (?:\ *\([0-9a-z]+\))+
                        (?:\ *[0-9a-z]+\.)*
                    )?
                )?

                # optionally hyphenated cite
                (?: \ *-\ *                           # hyphen in range of cites
                    # last cite (.section required here to avoid confusion with "3."):
                    (?: [0-9]+[A-Z][0-9]*-[0-9]+
                      | [0-9]{2,}
                    )
                    (?: \.[0-9]+
                        (?: (?:\ *\([0-9a-z]+\))+
                            (?:\ *[0-9a-z]+\.)*
                        )?
                    )?
                )?
              )*
            ) # end of citations

            # Optional suffix
            (?: [, ]*
                (?: F\.?S\.?
                  | F\.?A\.?C\.?
                  | Florida\ +[Ss]tatutes?
                  | Florida\ +[Aa]dministrative\ +[Cc]ode
                )
            )?
          """,
          re.VERBOSE | re.IGNORECASE)

fac_cite_re = re.compile(r"""
            # Citations are "section 719.106" or "subsection 61B-75.004", etc, and/or followed by
            # F.S. or F.A.C.

            # Optional Prefix:
            (?:(?:\b[sS]ections?|\b[sS]ubsections?|\b[pP]aragraphs?|\b[sS]ubparagraphs?
                 |\b[rR]ules?|\b[cC]hapters?)\ *)?

            # Capture all citation references as a group
            (

              # first cite:
              (?: [0-9]+[A-Z][0-9]*-[0-9]+            # 61B-75 or 61H1-20
                | [0-9]{2,}                           # or 719
              )
              (?:\.[0-9]+                             # optional: .106
                 (?: (?:\ *\([0-9a-z]+\))+            #   optional: one or more "(xx)"
                     (?:\ *[0-9a-z]+\.)*              #             any number of "xx."
                 )?
              )?

              # optionally hyphenated...
              (?: \ *-\ *                             # hyphen for range of cites
                  # last cite:
                  (?:
                      # full cite (.section required here to avoid confusion with "3.")
                      (?: [0-9]+[A-Z][0-9]*-[0-9]+
                        | [0-9]{2,}
                      )
                      (?: \.[0-9]+
                          (?: (?:\ *\([0-9a-z]+\))+
                              (?:\ *[0-9a-z]+\.)*
                          )?
                      )?
                    | # .nnn
                      (?:\.[0-9]+
                         (?: (?:\ *\([0-9a-z]+\))+
                             (?:\ *[0-9a-z]+\.)*
                         )?
                      )
                    | # (xx)
                      (?: (?:\ *\([0-9a-z]+\))+
                          (?:\ *[0-9a-z]+\.)*
                      )
                    | # x.
                      (?:\ *[0-9a-z]+\.)+
                  )
              )?

              # any number of "," and/or "and" seperated list of cites
              (?:
                (?: (?: , (?: \ *and)? \ *)           # , and? 
                  | (?: \ *and\ *))                   # and without ,

                # first cite:
                (?:
                    # full cite (.section required here to avoid confusion with "3.")
                    (?: [0-9]+[A-Z][0-9]*-[0-9]+
                      | [0-9]{2,}
                    )
                    (?: \.[0-9]+
                        (?: (?:\ *\([0-9a-z]+\))+
                            (?:\ *[0-9a-z]+\.)*
                        )?
                    )?
                  | # .nnn
                    (?:\.[0-9]+
                       (?: (?:\ *\([0-9a-z]+\))+
                           (?:\ *[0-9a-z]+\.)*
                       )?
                    )
                  | # (xx)
                    (?: (?:\ *\([0-9a-z]+\))+
                        (?:\ *[0-9a-z]+\.)*
                    )
                  | # x.
                    (?:\ *[0-9a-z]+\.)+
                )

                # optionally hyphenated cite
                (?: \ *-\ *                           # hyphen in range of cites
                    # last cite:
                    (?:
                        # full cite (.section required here to avoid confusion with "3.")
                        (?: [0-9]+[A-Z][0-9]*-[0-9]+
                          | [0-9]{2,}
                        )
                        (?: \.[0-9]+
                            (?: (?:\ *\([0-9a-z]+\))+
                                (?:\ *[0-9a-z]+\.)*
                            )?
                        )?
                      | # .nnn
                        (?:\.[0-9]+
                           (?: (?:\ *\([0-9a-z]+\))+
                               (?:\ *[0-9a-z]+\.)*
                           )?
                        )
                      | # (xx)
                        (?: (?:\ *\([0-9a-z]+\))+
                            (?:\ *[0-9a-z]+\.)*
                        )
                      | # x.
                        (?:\ *[0-9a-z]+\.)+
                    )
                )?
              )*

            ) # end of citations

            # Optional suffix
            (?: [, ]*
                (?: F\.?S\.?
                  | F\.?A\.?C\.?
                  | Florida\ +[Ss]tatutes?
                  | Florida\ +[Aa]dministrative\ +[Cc]ode
                )
            )?
          """,
          re.VERBOSE)

cite_re_map = {
    '719': [s_cite_re, ss_cite_re],
    '61b': [fac_cite_re],
}

cite_split_re = re.compile(r"""
                (?: (?: ,(?: \ *and)? \ * )           # , and? 
                  | (?: \ *and\ *))                   # and without ,
          """,
          re.VERBOSE)

cite_hyphen_re = re.compile(r"""
                (?:
                    # full cite (.section required here to avoid confusion with "3.")
                    (?: [0-9]+[A-Z][0-9]*-[0-9]+
                      | [0-9]{2,}
                    )
                    (?: \.[0-9]+
                        (?: (?:\ *\([0-9a-z]+\))+
                            (?:\ *[0-9a-z]+\.)*
                        )?
                    )?
                  | # .nnn
                    (?:\.[0-9]+
                       (?: (?:\ *\([0-9a-z]+\))+
                           (?:\ *[0-9a-z]+\.)*
                       )?
                    )
                  | # (xx)
                    (?: (?:\ *\([0-9a-z]+\))+
                        (?:\ *[0-9a-z]+\.)*
                    )
                  | # x.
                    (?:\ *[0-9a-z]+\.)+
                )
                \ *-
          """,
          re.VERBOSE)

def create_s_cites(para, text, trace):
    if trace:
        if para.item:
            citation = para.item.citation
        else:
            citation = para.cell.table.item.citation
        targets = [(m.group(), m.start(), m.end())
                   for m in re.finditer(r'719(\.[0-9]+)?|61[bB](-[0-9]+(\.[0-9]+)?)?', text)]
        if targets:
            for i in range(len(targets) - 1):
                if targets[i][1] > targets[i+1][1]:
                    print(f"create_s_cites {citation} WARNING {targets=} out of order")
            #print(f"create_s_cites {citation} {para.body_order=} {targets=}")

    # record all legal cites (starting with 'ss.' or 's.') in Annotations
    for m in chain.from_iterable(cite_re.finditer(text) for cite_re in cite_re_map[source]):
        start = m.start(1)
        end = m.end(1)
        if start == m.start() and end == m.end():
            #if not m.group().isdigit():
            #    print(f"create_s_cites: {citation} {para.body_order=} NOTICE: "
            #          f"no identifers on {m.group(1)} -- IGNORED")
            continue
        if trace:
            full = m.group().strip()
            if full.startswith('s.') or full.startswith('ss.'):
                print(f"  create_s_cites {citation} {para.body_order=} full starts with s.")
            first = None
            for i, (t_text, t_start, t_end) in enumerate(targets):
                if start <= t_start and end >= t_end:
                    if first is None:
                        first = i
                    last = i
            if first is None:
                print(f"  create_s_cites {citation} {para.body_order=} "
                      f"got cite {m.group(1)!r} at {start} -- NOTICE: NOT IN TARGETS")
            else:
                del targets[first: last + 1]
                print(f"  create_s_cites {citation} {para.body_order=} "
                      f"got cite {m.group(1)!r} at {start}")
        previous = None
        while True:
            comma = text.find(',', start, end)
            and_offset = text.find('and', start, end)
            if comma < 0 and and_offset < 0:
                # last cite
                cite = text[start: end]
                cite2 = cite.lstrip()
                start += len(cite) - len(cite2)  # add len of leading spaces
                cite = cite2.rstrip()
                previous, current = combine(previous, cite)
                if current:
                    if trace:
                        print(f"    create_s_cites: last cite {cite=!r} {current=!r} at {start}")
                    models.Annotation(paragraph=para, type='s_cite', char_offset=start,
                                      length=len(cite), info=current).save()
                break
            elif comma < 0 or 0 <= and_offset < comma:
                # and comes first
                cite = text[start: and_offset]
                cite2 = cite.lstrip()
                start += len(cite) - len(cite2)  # add len of leading spaces
                cite = cite2.rstrip()
                previous, current = combine(previous, cite)
                if current:
                    if trace:
                        print(f"    create_s_cites: and cite {cite=!r} {current=!r} at {start}")
                    models.Annotation(paragraph=para, type='s_cite', char_offset=start,
                                      length=len(cite), info=current).save()
                start = and_offset + 3
            else:
                # comma comes first
                cite = text[start: comma]
                cite2 = cite.lstrip()
                start += len(cite) - len(cite2)  # add len of leading spaces
                cite = cite2.rstrip()
                previous, current = combine(previous, cite)
                if current:
                    if trace:
                        print(f"    create_s_cites: ',' cite {cite=!r} {current=!r} at {start}")
                    models.Annotation(paragraph=para, type='s_cite', char_offset=start,
                                      length=len(cite), info=current).save()
                start = comma + 1
    if targets:
        print(f"  create_s_cites {citation} {para.body_order=} NOTICE done: {targets=}")

def combine(a, b):
    r'''Combines a (previous cite) with b.  Returns (previous, current) cites.

    Current may be hyphenated.

    Cite format is NNN.NNN(N)(A)N.A. or NNA-NN.NNN(N)(A)N.A.

    b might be just a new suffix for a.  If b starts with (N), then a NNN.NNN + b is taken.
    If b starts with (A), then a NNN.NNN(N) + b is taken.  Etc.

       >>> combine('', '123.456')
       ('123.456', '123.456')
       >>> combine('987.654', '61B-75.456 (1)')
       ('61B-75.456(1)', '61B-75.456(1)')
       >>> combine('987.654(6)(x)4.y.', '.456(1)')
       ('987.456(1)', '987.456(1)')
       >>> combine('987.654(6)(x)4.y.', ' ( 1)')
       ('987.654(1)', '987.654(1)')
       >>> combine('987.654(6)(x)4.y.', '(b )')
       ('987.654(6)(b)', '987.654(6)(b)')
       >>> combine('987.654(6)(x)4.y.', ' 3. ')
       ('987.654(6)(x)3.', '987.654(6)(x)3.')
       >>> combine('987.654(6)(x)4.y.', 'd.')
       ('987.654(6)(x)4.d.', '987.654(6)(x)4.d.')

    Also, b could have a hyphen in it indicating a range.

       >>> combine('987.654(6)(x)4.y.', 'd.-f.')
       ('987.654(6)(x)4.d.', '987.654(6)(x)4.d.-987.654(6)(x)4.f.')
    '''
    m = cite_hyphen_re.match(b)
    if not m:
        current = combine1(a, b)
        return current, current
    i = m.end() - 1
    first = combine1(a, b[:i])
    last = combine1(first, b[i + 1:])
    return first, f"{first}-{last}"


def combine1(a, b):
    r'''Combines a (previous) and b, returns current.
    '''
    b = b.replace(' ', '')
    if not a:
        return b
    if not b:
        return b
    try:
        if b.startswith('.'):
            return a[:a.index('.')] + b
        if b.startswith('('):
            if b[1].isdigit():
                return a[:a.index('(')] + b
            return a[:a.index(')') + 1] + b
        if b.endswith('.'):
            if b[0].isdigit():
                return a[:a.rindex(')') + 1] + b
            return a[:a.index('.', a.rindex(')')) + 1] + b
    except ValueError:
        print(f"combine1: WARNING ValueError for {a=!r} {b=!r}")
        #raise
    return b


def create_paragraph(text, body_order, item=None, cell=None, index=True, trace=True):
    assert item or cell
    para = models.Paragraph(item=item, cell=cell, body_order=body_order, text=text)
    para.save()
    if index:
        create_s_cites(para, text, trace)
    return para


def scrape_719(trace=False):
    r'''Organization of document:

    Section
      span SectionNumber: 719.103&emsp;
      span Catchline:
        span CatchlineText: Definitions.
        span EmDash: -
      span SectionBody:
        span ...: <text>
        div Subsection
          span Number: (1)&emsp;
          span ...: <text>
          div Paragraph
            span Number: (a)&emsp;
            span ...: <text>
            div SubParagraph
              span Number: 1.&emsp;
              span ...: <text>
              div SubSubParagraph
                span Number: a.&emsp;
                span ...: <text>
    '''
    global item_order
    print(f"scrape_719 {trace=}")
    soup = get(chapter_719)
    chapter = find1(soup, 'div', recursive=True, class_='Chapter')
    item_order = 1
    for part in chapter.find_all('div', recursive=False, class_='Part'):
        process_part(part, trace)

def process_part(part, trace):
    pt = find1(part, 'div', class_="PartTitle")
    number = get_string(find1(pt, 'div', class_="PartNumber"), de_emsp=True)
    type = "Part"
    title = get_string(find1(pt, 'span', class_="PartTitle"))
    if trace:
        print(f"{type}: {item_order=}, {number=}, {title=}")
    part_obj = create_item(number, number, title)
    body_order = 0  # in case there are no children...
    for body_order, section \
     in enumerate(part.find_all('div', recursive=False, class_='Section'), 1):
        process_section(section, part_obj, body_order, trace)
    set_num_elements(part_obj, body_order)


def process_section(section, parent, body_order, trace):
    r'''

    Section citations have a space at the end so that citation prefixes can be used to
    determine whether Item A is a parent (recursively) of Item B.  This prevents '719.103'
    from being taken as a parent of '719.1035'.
    '''
    #print("process_section:")
    #print(section.prettify())
    assert len(section.contents) > 1, \
           f"process_section {parent.citation=}, expected > 1 contents, " \
           f"got {len(section.contents)}"

    assert section.contents[0].name == 'span', \
           f"process_section {parent.citation=}, expected 'span' contents0, " \
           f"got {section.contents[0].name}"
    assert 'SectionNumber' in section.contents[0]['class'], \
           f"process_section {parent.citation=}, expected 'SectionNumber' contents0, " \
           f"got {section.contents[0]['class']}"
    number = get_string(section.contents[0], de_emsp=True).strip() + ' '

    type = "Section"

    assert section.contents[1].name == 'span', \
           f"process_section {parent.citation=}, expected 'span' contents1, " \
           f"got {section.contents[1].name}"
    assert 'Catchline' in section.contents[1]['class'], \
           f"process_section {parent.citation=}, expected 'Catchline' contents1, " \
           f"got {section.contents[1]['class']}"
    title = get_string(section.contents[1], ignore_emdash=True)
    assert title

    #if number == '719.108 ':
    #    print(f"{number=}, turning on trace")
    #    trace = True

    if trace:
        print(f"{type}: citation={number}, {parent.citation=}, {item_order=}, "
              f"{body_order=}, {title=}")

    assert number[-1] == ' '

    # omitting part number from citation
    section_obj = create_item(number, number.strip(), title, parent, body_order)

    get_body(find1(section, 'span', class_="SectionBody"),
             parent=section_obj,
             allow_title=False,
             trace=trace)
    body_order = section_obj.num_elements + 1
    history = get_history(find1(section, 'div', class_="History"))
    if history:
        if trace:
            print(f"{type}: citation={number} -> {history=}")
        assert not history.startswith('History'), \
               f"process_section {section_obj.citation} {history=!r}"
        create_note(section_obj, body_order, 'History. ' + history, 8)
        body_order += 1
    for body_order, note in enumerate(section.find_all('div', recursive=False, class_="Note"),
                                      body_order):
        number = note.sup.a.string
        text = note.contents[-1].string
        assert not text.startswith('Note.'), \
               f"process_section {section_obj.citation} note {number=} {text=!r}"
        create_note(section_obj, body_order, 'Note. ' + text, 5, info=number)

def create_note(parent, body_order, text, prefix_len=None, type=None, info=None):
    if type is None:
        assert prefix_len is not None
        type = text[:prefix_len]
        if type[-1] == '.':
            type = type[:-1]
        type = type.lower().replace(' ', '_')
    elif prefix_len is None:
        prefix_len = len(text)
    para = create_paragraph(text, body_order, parent, index=(type not in ('citeAs', 'history')))
    models.Annotation(paragraph=para, type=type, char_offset=0, length=prefix_len, info=info) \
          .save()

def get_string(tag, de_emsp=False, ignore_emdash=False, allow_p=False):
    span = []
    def get_strings(tag, de_emsp, ignore_emdash, depth=0):
        if isinstance(tag, NavigableString):
            #print("NavString", str(tag))
            span.append(drop_emsp(str(tag), de_emsp))
        elif tag.name in ('span', 'b', 'br'):
            if tag.has_attr('class') and 'EmDash' in tag['class']:
                if not ignore_emdash:
                    print(f"=== WARNING: get_strings {depth=} got non-ignored EmDash")
            else:
                for child in tag.children:
                    get_strings(child, de_emsp, ignore_emdash, depth + 1)
        elif tag.name == 'p' and allow_p:
            for child in tag.children:
                get_strings(child, de_emsp, ignore_emdash, depth + 1)
        else:
            print("get_strings:", tag.prettify())
            print(f"=== WARNING: get_strings {depth=} expected 'span', "
                  f"got {tag.name=} -- IGNORED")
    for child in tag.children:
        get_strings(child, de_emsp, ignore_emdash)
    #if len(span) > 1:
    #    print("get_string:", span)
    return ' '.join(span)

def drop_emsp(s, de_emsp=True):
    i = s.find(emsp)
    if i >= 0:
        if not de_emsp or i != len(s) - 1:  # not last char in s
            #print(f"=== WARNING: Embedded emsp in {s!r} -- not dropped")
            return s
        #print(f"Found emsp in {s=}")
        return s[:-1]
    return s


word_re = re.compile(r'[a-zA-Z0-9]*')

def get_body(tag, parent=None, allow_title=True, skip=0, strip=0, trace=False):
    r'''Returns title.

    Calls process_child in divs if there is a parent.
    '''
    #print(f"get_body: {parent.citation=}, {tag.name=}, {tag['class']=}")
    #print(tag.prettify())

    title = None
    body_order = 1
    current_span = []
    annotations = []

    def end_span():
        nonlocal body_order, current_span, annotations
        if current_span:
            text = ' '.join(current_span)
            p = create_paragraph(text, body_order, parent)
            body_order += 1

            # record annotations
            for offset, type, info in annotations:
                m = s_cite_re.match(text, offset)
                if not m:
                    m = ss_cite_re.match(text, offset)
                    if not m:
                        m = word_re.match(text, offset)
                models.Annotation(paragraph=p, type=type, char_offset=offset,
                                  length=m.end() - offset, info=info).save()
            annotations = []
            current_span = []

    def flatten(tag, depth=0, nav=None, skip=0):
        nonlocal title, body_order, current_span, annotations, strip
        if tag.name == 'span' and 'EmDash' in tag['class']:
            print("EmDash in", parent.citation, "depth", depth)
            assert body_order == 1
            assert len(current_span) == 1
            assert allow_title
            title = ' '.join(current_span)
            current_span = []
            return
        for child in tag.contents[skip:]:
            if isinstance(child, NavigableString):
                #print("NavString", str(child))
                current_span.append(drop_emsp(str(child)).strip())
            elif child.name == 'span':
                if 'Number' in child['class']:
                    print(f"=== WARNING: get_body {parent.citation=} {depth=} "
                          f"got Number span")
                flatten(child, depth+1)
            elif child.name == 'sup':
                annotations.append(
                  (sum(len(s) for s in current_span) + len(current_span),
                   'note_ref', child.a.string))
            elif child.name == 'p':
                end_span()
                flatten(child, depth+1)
                end_span()
            elif child.name == 'div':
                #print("div in parent", parent.citation, "at depth", depth)
                end_span()
                if parent is None:
                    print(f"=== WARNING: flatten parent=None got unexpected div "
                          f"{child.get('class')} -- IGNORED")
                else:
                    process_child(parent, child, strip, body_order, trace)
                    body_order += 1
                    strip = 0
            elif child.name == 'table':
                end_span()
                assert strip == 0
                if parent is None:
                    print(f"=== WARNING: flatten parent=None got unexpected table "
                          f"{child.get('class')} -- IGNORED")
                else:
                    #print(f"flatten {parent.citation=} {depth=} got table")
                    process_table(parent, child, body_order)
                    body_order += 1
            elif child.name == 'br':
                end_span()
            else:
                print(f"=== WARNING: flatten {parent.citation=} got unexpected {child.name} "
                      f"{child.get('class')} -- IGNORED")

    flatten(tag, skip=skip)
    end_span()
    set_num_elements(parent, body_order - 1)
    return title


def process_child(parent, child, strip_number, body_order, trace):
    #print(f"process_child {parent.citation=}, {child=}")
    type = child['class'][0]

    allow_title, skip, strip, number = get_number(child, strip_number, trace)
    if allow_title:
        strip = 0
    my_citation = f"{parent.citation}{number}"
    if trace:
        print(f"{type}: citation={my_citation}, {item_order=}, {body_order=}, "
              f"{parent.citation=}")
    obj = create_item(my_citation, number, None, parent, body_order)
    title = get_body(child, parent=obj, allow_title=allow_title, skip=skip,
                     strip=strip, trace=trace)
    if title:
        if trace:
            print(f"{type}: citation={my_citation} -> {title=}")
        create_paragraph(title, 0, obj)
        obj.has_title = True
        obj.save()

def get_number(tag, strip_number, trace):
    r'''Returns allow_title, skip, strip, number.

    allow_title is for the next call to get_body.
    skip is the number of children for the next get_body to skip.
    strip is the number of chars to delete on the front of number for the next subparagraph.
    number is the number for this paragraph.
    '''
    contents0 = tag.contents[0]
    if trace:
        print(f"get_number: {strip_number=} first child is {contents0.name}")
        #print(tag.prettify())
    if contents0.name == 'span':
        assert 'Number' in contents0['class'], \
               f"get_number got span, expected 'class' of ['Number'], " \
               f"got {contents0['class']}"
        number = get_string(contents0, de_emsp=True).strip()
        if trace:
            print(f"get_number: got Number span, number in span is {number=}, "
                  f"{strip_number=}")
        number = number[strip_number:]
        if trace:
            print(f"  -> {strip_number=}, {number=}")
            print(f"  returning True, 1, {strip_number=}, {number=}")
        return True, 1, strip_number, number
    # My number included on first sub div number!
    assert contents0.name == 'div', \
           f"get_number expected contents[0] of 'span' or 'div', got {contents0.name}"
    assert contents0.contents, f"get_number first div has no contents"
    _, _, strip, child_number = get_number(contents0, strip_number, trace)
    if strip < len(child_number):
        if child_number[0] == '(':
            index = child_number.index(')') + 1
        else:
            assert child_number[0].isdigit(), \
                   f"get_number {child_number=} expected '(' or digit " \
                   f"for first char, got {child_number[0]}"
            index = child_number.index('.') + 1
        if trace:
            print(f"{strip=} < {len(child_number)=}: "
                  f"stripping first number in {child_number=}, got {index=}")
            print(f"  {strip=}, {child_number=}, {index=}")
            print(f"  -> strip={strip + index}, number={child_number[:index]}")
        if index >= len(child_number):
            if trace:
                print(f"{index=} >= {len(child_number)=}: returning False, 0, 0, "
                      f"{child_number[:index]}")
            return False, 0, 0, child_number[:index]
        if trace:
            print(f"{index=} < {len(child_number)=}: returning False, 0, "
                  f"{strip + index}, {child_number[:index]}")
        return False, 0, strip + index, child_number[:index]
    if trace:
        print(f"{strip=} >= {len(child_number)=} -> {strip=}, number={child_number}")
        print(f"didn't strip first number from {child_number=}: "
              f"returning False, 0, {strip}, {child_number}")
    return False, 0, strip, child_number

def get_history(tag):
    # FIX: for now...
    return get_string(find1(tag, 'span', class_='HistoryText'))

def process_table(parent, child, body_order):
    table = models.Table(item=parent, has_header=False, body_order=body_order)
    table.save()
    row = 1
    def load_row(tr, head=False):
        nonlocal row
        for col_num, col in enumerate(tr, 1):
            cell = models.TableCell(table=table, row=row, col=col_num)
            cell.save()
            if head and not table.has_header:
                table.has_header = True
                table.save()

            text = ''
            i = 1
            for x in col:
                if isinstance(x, NavigableString) or x.name != 'p':
                    text = text_cat(text, get_string(col))
                else:  # <p> tag
                    if text:
                        create_paragraph(text, i, cell=cell)
                        i += 1
                        text = ''
                    create_paragraph(get_string(x), i, cell=cell)
                    i += 1
            #print(f"process_table: inserting TableCell {table.id=}, {head=}, {row=}, "
            #      f"col={col_num}, {text=}")
            if text:
                create_paragraph(text, i, cell=cell)
        row += 1
    head = child.thead
    if head:
        load_row(head.tr, head=True)
    body = child.tbody
    def load_rows(tag):
        for r in tag.children:
            load_row(r)
    if body:
        load_rows(body)
    else:
        load_rows(child)

@transaction.atomic
def run(*args):
    global source, version_obj
    if not args or 'help' in args:
        print("scrape_html help")
        print("  manage.py runscript scrape_html --script-args help")
        print("    prints this help message")
        print("  manage.py runscript scrape_html --script-args doctests")
        print("    run doctests on this module")
        print("  manage.py runscript scrape_html --script-args 719")
        print("    - loads chapter 719 as a new version with today's date")
        print("    - you must also runscript load_words --script-args <version_id>")
        print("      to index all of the words in this new version")
        print("  manage.py runscript scrape_html --script-args 61b")
        print("    - loads chapter 61B-75 to 79 as a new version with today's date")
        print("    - you must also runscript load_words --script-args <version_id>")
        print("      to index all of the words in this new version")
        print("  manage.py runscript scrape_html --script-args trace")
        print("    turns trace on for the load")
    elif 'doctests' in args:
        import doctest
        print(f"{doctest.testmod()=}")
    elif 'test' in args:
        for s in 'in s. 719.504.', 'to s. 719.301(4).', 'to s. 719.108(3)(b)3.':
            m = s_cite_re.search(s)
            if m is None:
                print(f"search failed for {s!r}")
            else:
                print(f"search matched {s=!r} with {m.group()=!r}")
    elif '719' in args:
        print(f"run {args=}")
        version_obj = models.Version(source=fl_leg_domain, url=chapter_719)
        version_obj.save()
        source = '719'
        scrape_719('trace' in args)
        print("Chapter 719 loaded as version", version_obj.id)
        print(f"next: python manage.py runscript load_words --script-args {version_obj.id}")
    elif '61b' in [s.lower() for s in args]:
        print(f"run {args=}")
        version_obj = models.Version(source=casetext_domain, url=casetext_61B)
        version_obj.save()
        source = '61b'
        scrape_61B('trace' in args)
        print("Chapters 61B-75 through 79 loaded as version", version_obj.id)
        print(f"next: python manage.py runscript load_words --script-args {version_obj.id}")

