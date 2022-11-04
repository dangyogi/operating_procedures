# scrape_html.py

import re

import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from django.db import transaction

from operating_procedures import models


casetext = "https://casetext.com/"
casetext_61B = casetext + \
                 "regulation/florida-administrative-code/" \
                 "department-61-department-of-business-and-professional-regulation/" \
                 "division-61b-division-of-florida-condominiums-timeshares-and-mobile-homes"

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

def scrape_61B():
    r'''Expectes a list of chapters.  Passes all 75-79 chapters to process.
    '''
    soup = get(casetext_61B)
    article = find1(soup, 'article', recursive=True)
    ul = find1(article, 'ul')
    for a in ul.find_all('a'):
        title = find1(a, 'span', recursive=True, class_='title').string
        assert title.startswith('Chapter 61B-')
        ch_number = int(title[12:].split()[0])
        if 75 <= ch_number <= 79:
            if 'Repealed' not in title:
                href = a['href']
                if href[0] != '/':
                    href = casetext + href
                process(ch_number, title, href)


def process(ch_number, title, url):
    print(ch_number, title, url)


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
    global item_order
    pt = find1(part, 'div', class_="PartTitle")
    number = get_string(find1(pt, 'div', class_="PartNumber"), de_emsp=True)
    type = "Part"
    title = get_string(find1(pt, 'span', class_="PartTitle"))
    if trace:
        print(f"{type}: {item_order=}, {number=}, {title=}")
    part_obj = models.Item(version=version_obj, item_order=item_order, num_elements=0,
                           citation=number, number=number, has_title=True)
    part_obj.save()
    p = models.Paragraph(item=part_obj, body_order=0, text=title)
    p.save()
    item_order += 1
    body_order = 0  # in case there are no children...
    for body_order, section \
     in enumerate(part.find_all('div', recursive=False, class_='Section'), 1):
        process_section(section, part_obj, body_order, trace)
    if body_order:
        part_obj.num_elements = body_order
        part_obj.save()
    

def process_section(section, parent, body_order, trace):
    r'''

    Section citations have a space at the end so that citation prefixes can be used to
    determine whether Item A is a parent (recursively) of Item B.  This prevents '719.103'
    from being taken as a parent of '719.1035'.
    '''
    global item_order
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
    section_obj = models.Item(version=version_obj, citation=number, number=number.strip(),
                              parent=parent, item_order=item_order, body_order=body_order,
                              num_elements=0, has_title=True)

    section_obj.save()
    p = models.Paragraph(item=section_obj, body_order=0, text=title)
    p.save()

    item_order += 1

    get_body(find1(section, 'span', class_="SectionBody"),
             parent=section_obj,
             allow_title=False,
             trace=trace)
    history = get_history(find1(section, 'div', class_="History"))
    if history:
        if trace:
            print(f"{type}: citation={number} -> {history=}")
        section_obj.history = history
        section_obj.save()
    notes = []
    for note in section.find_all('div', recursive=False, class_="Note"):
        note_obj = models.Note(item=section_obj, number=note.sup.a.string,
                               text=note.contents[-1].string)
        note_obj.save()

def get_string(tag, de_emsp=False, ignore_emdash=False):
    span = []
    def get_strings(tag, de_emsp, ignore_emdash, depth=0):
        if isinstance(tag, NavigableString):
            #print("NavString", str(tag))
            span.append(drop_emsp(str(tag), de_emsp))
        elif tag.name in ('span', 'br'):
            if tag.has_attr('class') and 'EmDash' in tag['class']:
                if not ignore_emdash:
                    print(f"=== WARNING: get_strings {depth=} got non-ignored EmDash")
            else:
                for child in tag.children:
                    get_strings(child, de_emsp, ignore_emdash, depth + 1)
        else:
            print("get_strings:", tag.prettify())
            print(f"=== WARNING: get_strings {depth=} expected 'span', "
                  f"got {tag.name=} -- ignored")
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

cite_re = re.compile(r"""
            (?:ss?\.|section)\     # Citations are "s. 719.106" or "section 719.106"
                                   # or "ss. 719.106, 719.107 and 719.109"
                                   # or "ss. 719.106-719.108"
            (                      # capture citation references as group

              # first cite:
              [0-9]+\.[0-9]+         # 719.106
              (?:\([0-9a-zA-Z]+\))*  # any number of "(xx)"
              (?:[0-9a-zA-Z]+\.)*    # any number of "xx."

              # optionally hyphenated...
              (?: \ *-\ *            # hyphen for range of cites
                  [0-9]+\.[0-9]+         
                  (?:\([0-9a-zA-Z]+\))*  
                  (?:[0-9a-zA-Z]+\.)*)?

              # any number of "," and/or "and" seperated list of cites
              (?:
                (?: (?: ,(?: \ *and)? \ * )  # , and? 
                | (?: \ *and\ *))            # and without ,

                # first cite
                [0-9]+\.[0-9]+         # 719.106
                (?:\([0-9a-zA-Z]+\))*  # any number of "(xx)"
                (?:[0-9a-zA-Z]+\.)*    # any number of "xx."

                # optionally hyphenated cite
                (?: \ *-\ *            # hyphen in range of cites
                    [0-9]+\.[0-9]+         
                    (?:\([0-9a-zA-Z]+\))*  
                    (?:[0-9a-zA-Z]+\.)*)?
              )*

            )                      # end of citation
          """,
          re.VERBOSE | re.IGNORECASE)
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
            p = models.Paragraph(item=parent, body_order=body_order, text=text)
            p.save()
            body_order += 1

            # record all legal cites (starting with 'ss.' or 's.') in Annotations
            for m in cite_re.finditer(text):
                cites = m.group(1)
                start = m.start(1)
                end = m.end(1)
                if trace:
                    print(f"end_span: got cite {cites!r} at {start}")
                while True:
                    comma = text.find(',', start, end)
                    and_offset = text.find('and', start, end)
                    if comma < 0 and and_offset < 0:
                        # last cite
                        cite = text[start: end]
                        cite2 = cite.lstrip()
                        start += len(cite) - len(cite2)  # add len of leading spaces
                        cite = cite2.rstrip()
                        if trace:
                            print(f"end_span: last cite {cite!r} at {start}")
                        models.Annotation(paragraph=p, type='s_cite', char_offset=start,
                                          length=len(cite), info=cite).save()
                        break
                    elif comma < 0 or and_offset < comma:
                        # and comes first
                        cite = text[start: and_offset]
                        cite2 = cite.lstrip()
                        start += len(cite) - len(cite2)  # add len of leading spaces
                        cite = cite2.rstrip()
                        if trace:
                            print(f"end_span: 'and' cite {cite!r} at {start}")
                        models.Annotation(paragraph=p, type='s_cite', char_offset=start,
                                          length=len(cite), info=cite).save()
                        start = and_offset + 3
                    else:
                        # comma comes first
                        cite = text[start: comma]
                        cite2 = cite.lstrip()
                        start += len(cite) - len(cite2)  # add len of leading spaces
                        cite = cite2.rstrip()
                        if trace:
                            print(f"end_span: ',' cite {cite!r} at {start}")
                        if cite:  # cite will be '' if , and encountered...
                            models.Annotation(paragraph=p, type='s_cite', char_offset=start,
                                              length=len(cite), info=cite).save()
                        start = comma + 1

            # record annotations
            for offset, type, info in annotations:
                m = cite_re.match(text, offset)
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
                   'note', child.a.string))
            elif child.name == 'p':
                end_span()
                flatten(child, depth+1)
                end_span()
            elif child.name == 'div':
                #print("div in parent", parent.citation, "at depth", depth)
                end_span()
                if parent is None:
                    print(f"=== WARNING: flatten parent=None got unexpected div "
                          f"{child.get('class')} -- ignored")
                else:
                    process_child(parent, child, strip, body_order, trace)
                    body_order += 1
                    strip = 0
            elif child.name == 'table':
                end_span()
                assert strip == 0
                if parent is None:
                    print(f"=== WARNING: flatten parent=None got unexpected table "
                          f"{child.get('class')} -- ignored")
                else:
                    #print(f"flatten {parent.citation=} {depth=} got table")
                    process_table(parent, child, body_order)
                    body_order += 1
            elif child.name == 'br':
                end_span()
            else:
                print(f"=== WARNING: flatten {parent.citation=} got unexpected {child.name} "
                      f"{child.get('class')} -- ignored")

    flatten(tag, skip=skip)
    end_span()
    if body_order > 1:
        parent.num_elements = body_order - 1
        parent.save()
    return title


def process_child(parent, child, strip_number, body_order, trace):
    global item_order
    #print(f"process_child {parent.citation=}, {child=}")
    type = child['class'][0]

    allow_title, skip, strip, number = get_number(child, strip_number, trace)
    if allow_title:
        strip = 0
    my_number = f"{parent.citation}{number}"
    if trace:
        print(f"{type}: citation={my_number}, {item_order=}, {body_order=}, "
              f"{parent.citation=}")
    obj = models.Item(version=version_obj, citation=my_number, number=number, parent=parent,
                      item_order=item_order, body_order=body_order, num_elements=0)
    obj.save()
    item_order += 1
    title = get_body(child, parent=obj, allow_title=allow_title, skip=skip,
                     strip=strip, trace=trace)
    if title:
        if trace:
            print(f"{type}: citation={my_number} -> {title=}")
        p = models.Paragraph(item=obj, body_order=0, text=title)
        p.save()
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
        for i, col in enumerate(tr, 1):
            text = get_string(col)
            #print(f"process_table: inserting TableCell {table.id=}, {head=}, {row=}, "
            #      f"col={i}, {text=}")
            cell = models.TableCell(table=table, row=row, col=i)
            cell.save()
            if head and not table.has_header:
                table.has_header = True
                table.save()
            p = models.Paragraph(cell=cell, body_order=1, text=text)
            p.save()
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
    global version_obj
    if 'help' in args:
        print("scrape_719 help")
        print("  manage.py runscript scrape_719 --script-args help")
        print("    prints this help message")
        print("  manage.py runscript scrape_719")
        print("    - loads chapter 719 as a new version with today's date")
        print("    - you must also runscript load_words --script-args <version_id>")
        print("      to index all of the words in this new version")
        print("  manage.py runscript scrape_719 --script-args trace")
        print("    turns trace on for the load")
    else:
        print(f"run {args=}")
        version_obj = models.Version(source=fl_leg_domain, url=chapter_719)
        version_obj.save()
        scrape_719('trace' in args)
        print("Chapter 719 loaded as version", version_obj.id)
        print(f"next: python manage.py runscript load_words")

