# scrape_bylaws.py

from pathlib import Path
import re

from django.db import transaction

from operating_procedures import models


Source = 'officialrecords.mypinellasclerk.org'
Source_file = Path(__file__).parents[2] / 'bylaws.txt'


def get_line(skip_blank_lines=False):
    r'''Returns None at EOF.
    '''
    while True:
        line = Infile.readline()
        if not line: return None
        if '##' in line:
            line = line[: line.index('##')]
        line = line.rstrip()
        if line or not skip_blank_lines:
            return line

Item_re = re.compile(r'(ARTICLE [IVX]+|[0-9]{1,2}(?:\.[0-9]*)?|[a-z]\.)(?: +(.*)|(?![0-9a-zA-Z]))')

def scrape(trace=False):
    r'''Expects a list of articles.
    '''
    global Infile, History
    item_order = 0
    History = []   # list of [item, body_order]
    with Source_file.open() as Infile:
        line = get_line(skip_blank_lines=True)  # None at EOF
        while line is not None and not line.startswith('--END--'):
            item_order += 1
            process_item(line, item_order, trace)
            line = get_line(skip_blank_lines=True)  # None at EOF
        while History:
            set_num_elements(trace)


def process_item(line, item_order, trace):
    global History

    m = Item_re.match(line)
    if m:
        number = m.group(1)
        title = m.group(2)
        #print(f"next item {number=} {item_order=} {History=} {title=}")
        if number.startswith('ARTICLE '):
            # top-level item
            #print(f"process_item got ARTICLE {line=!r}")
            citation = number
            History = []
        elif '.' not in number or number.endswith('.'):
            # 1 or 1.
            assert number.count('.') <= 1, f"Expected n or n., got {number=}"
            if not number.endswith('.'):
                number += '.'
            if History[-1][0].number.count('.') == 1 and History[-1][0].number.endswith('.'):
                # History[-1] is 'x.', but not '1.1.'
                if number[0].isdigit() == History[-1][0].number[0].isdigit():
                    # At the same level, del prior sibling
                    #print(f"process_item got {number!r} with prior matching "
                    #      f"{History[-1][0].citation!r} -- same level {line=!r}")
                    #print(f"process_item popping {History[-1][0].citation=!r}")
                    set_num_elements(trace)
                elif History[-1][0].citation.count('.') == 1 or number[0].isdigit():
                    # We're decending down another level
                    #print(f"process_item got n. {number} with prior a. {History[-1][0].citation} "
                    #      f"-- down a level {line=!r}")
                    pass
                else:
                    # We're going up a level
                    #print(f"process_item got a. {number} with prior {History[-1][0].citation} "
                    #      f"-- up a level {line=!r}")
                    # del prior nephew and prior sibling
                    #print(f"process_item popping {History[-1][0].citation=!r} and "
                    #      f"{History[-2][0].citation=!r}")
                    set_num_elements(trace)
                    set_num_elements(trace)
                citation = History[-1][0].citation + number
            elif '.' in History[-1][0].number:  # History[-1] is 1.1.
                # We're decending down another level
                #print(f"process_item got {number} with prior n.n {History[-1][0].citation} "
                #      f"-- down a level {line=!r}")
                assert History[-1][0].number.count('.') == 2, \
                       f"Expected n.n, got {History[-1][0].number=}"
                citation = History[-1][0].citation + number
            else:
                #print(f"process_item got {number} with prior Article {History[-1][0].number} "
                #      f"-- down a level {line=!r}")
                assert History[-1][0].number.startswith('ARTICLE '), \
                       f"Expected ARTICLE in History, got {History[-1][0].number=}"
                # We're decending down another level
                citation = number
        else:
            # 1.1
            #print(f"process_item got n.n {number} -- at level {len(History)} {line=!r}")
            assert number.count('.') == 1, f"Expected n.n, Got {number=}"
            while len(History) > 1:
                #print(f"process_item popping {History[-1][0].citation=!r}")
                set_num_elements(trace)
            number += '.'
            citation = number

        if History:
            History[-1][1] += 1
            last_item = create_item(citation, number, title, item_order, History[-1][0],
                                    History[-1][1], trace=trace)
        else:
            last_item = create_item(citation, number, title, item_order, trace=trace)
        History.append([last_item, 0])
    else:
        raise AssertionError(f"Item_re failed match against first line in block {line[:20]=}")
        #assert History, f"Item_re failed match against first line {line[:20]=}"
    process_paragraphs(trace)


def process_paragraphs(trace):
    text = ''
    def check_text():
        nonlocal text
        if text:
            History[-1][1] += 1
            create_paragraph(History[-1][0], History[-1][1], text, trace)
            text = ''
    line = get_line()
    while line:
        if line == '-':
            check_text()
        elif line == '<':
            check_text()
            set_num_elements(trace)
        else:
            if text:
                text = ' '.join((text, line))
            else:
                text = line
        line = get_line()
    check_text()


def create_item(citation, number, title, item_order, parent=None, body_order=None, trace=False):
    if trace:
        print(f"create_item {citation=} {number=} {title=} {item_order=}")
        item = citation
    else:
        #print(f"create_item {citation=} parent={parent and parent.citation} {item_order=} "
        #      f"{body_order=}")
        item = models.Item.objects.create(version=version_obj, citation=citation,
                                          number=number, parent=parent,
                                          item_order=item_order, body_order=body_order,
                                          num_elements=0, has_title=bool(title))
    if title:
        create_paragraph(item, 0, title, trace)
    return item


def set_num_elements(trace):
    r'''Sets num_elements for last item in History, and pops it from History.
    '''
    item, num_elements = History.pop()
    if num_elements > 0:
        if trace:
            print(f"set_num_elements {item=} {num_elements=}")
        else:
            item.num_elements = num_elements
            item.save()


def create_paragraph(item, body_order, text, trace):
    if trace:
        print(f"create_paragraph {item=} {body_order=} {text[:20]=}")
        para = f"{item} {text[:20]}"
        citation = item
    else:
        para = models.Paragraph.objects.create(item=item,
                                               body_order=body_order,
                                               text=text)
        citation = item.citation
    create_cites(citation, para, text, trace)


cite_re = re.compile(r"""
            # Citations are [ S#:]NNN?.NNN ([AN])*

            # s. Prefix:
            [ S#:]

            # Capture citation reference as a group
            (
              # cite:
              [0-9]{2,}\.[0-9]+                       # NN.NN
              (?:\.?\ *\([a-z0-9]{1,2}\))*            # .?([AN])*
              (?:\ *[a-z0-9]{1,2}\.)*                 # x.*
              (?:\ *[0-9]{1,2})*                      # N*
            ) # end of citation
          """,
          re.VERBOSE)

def create_cites(citation, para, text, trace):
    targets = [(m.group(), m.start(), m.end())
               for m in re.finditer(r'[0-9]{2,3}(\.[0-9]+)?', text)]
    if targets:
        for i in range(len(targets) - 1):
            if targets[i][1] > targets[i+1][1]:
                print(f"create_cites {citation} WARNING {targets=} out of order")
        #print(f"create_cites {citation} {para.body_order=} {targets=}")

    # record all legal cites (starting with 'ss.' or 's.') in Annotations
    for m in cite_re.finditer(text):
        start = m.start(1)
        end = m.end(1)
        if trace:
            full = m.group().strip()
            print(f"  create_cites {citation} {para.body_order=} {full[0]=}")
        first = None
        for i, (t_text, t_start, t_end) in enumerate(targets):
            if start <= t_start and end >= t_end:
                if first is None:
                    first = i
                last = i
        if first is None:
            print(f"create_cites {citation} {para.body_order=} "
                  f"got cite {m.group(1)!r} at {start} -- NOTICE: NOT IN TARGETS")
        else:
            del targets[first: last + 1]
            if trace:
                print(f"create_cites {citation} {para.body_order=} "
                      f"got cite {m.group(1)!r} at {start}")

        cite = text[start: end]
        cite2 = cite.replace(' ', '')
        cite3 = cite2.replace('.(', '(')
        while cite3.count('(') > 2:
            cite3 = ''.join(cite2.rsplit('(', 1))   # delete last '('
            cite3 = '.'.join(cite3.rsplit(')', 1))  # replace last ')' with '.'
        if '(' in cite3 and not cite3.endswith(')') and not cite3.endswith('.'):
            cite3 += '.'
        if trace and cite2 != cite3:
            print(f"create_cites: {cite2} -> {cite3}")
        if trace:
            print(f"  create_cites: {cite2=!r} at {start}")
        else:
            models.Annotation.objects.create(paragraph=para,
                                             type='s_cite',
                                             char_offset=start,
                                             length=len(cite),
                                             info=cite2)

    if trace and targets:
        print(f"create_cites {citation} NOTICE done: {targets=}")


@transaction.atomic
def run(*args):
    global version_obj
    if 'help' in args:
        print("scrape_bylaws help")
        print("  python manage.py runscript scrape_bylaws")
        print("    - loads bylaws as a new version with today's date")
        print("    - you must also runscript load_words --script-args <version_id>")
        print("      to index all of the words in this new version")
        print("  python manage.py runscript scrape_bylaws --script-args trace")
        print("    turns trace on for the load")
        print("  python manage.py runscript scrape_bylaws --script-args test")
        print("    runs test instead of scraping bylaws")
        print("  python manage.py runscript scrape_bylaws --script-args help")
        print("    prints this help message")
    elif 'test' in args:
        for s in ('ARTICLE II', 'ARTICLE II TITLE STRING', '1.1', '1.1 Title string:',
                  '1.', 'a.'
        ):
            m = Item_re.match(s)
            if m is None:
                print(f"Item_re match failed for {s!r}")
            else:
                print(f"Item_re matched {s=!r} with {m.group(1)=!r} {m.group(2)=}")
    elif 'trace' in args:
        print(f"run {args=}")
        scrape(trace=True)
    else:
        version_obj = models.Version(source=Source)
        version_obj.save()
        scrape()
        print("Bylaws loaded as version", version_obj.id)
        print(f"next: python manage.py runscript load_words --script-args gg")

