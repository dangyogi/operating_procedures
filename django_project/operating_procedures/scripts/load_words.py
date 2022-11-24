# load_words.py

import re

from django.db import transaction

from operating_procedures import models
from operating_procedures.scripts.sources import *


def index_paragraph(paragraph):
    global words
    for sentence_number, (sentence_offset, s) in enumerate(get_sentences(paragraph.text), 1):
        for word_number, (word_offset, w) in enumerate(get_words(s), 1):
            word_id = models.Word.lookup_word(w).id
            models.WordRef(paragraph=paragraph,
                           word_id=word_id,
                           sentence_number=sentence_number,
                           word_number=word_number,
                           char_offset=sentence_offset + word_offset,
                           length=len(w)).save()

def index_cell(cell):
    for p in cell.paragraph_set.all():
        index_paragraph(p)


def get_sentences(text, trace=False):
    start = 0
    while True:
        if trace:
            print(f"first loop {start=}, {len(text)=}")
        sentence_start = start
        while True:
            end = text.find('.', start)
            if trace:
                print(f"second loop {sentence_start=}, {start=}, {end=}")
            if end < 0:
                if trace:
                    print(f"get_sentences last segment -> {text[sentence_start:]}")
                yield sentence_start, text[sentence_start:]
                return
            elif check_end(text, sentence_start, end, trace):
                if trace:
                    print(f"get_sentences -> {text[sentence_start: end]}")
                yield sentence_start, text[sentence_start: end]
                start = end + 1
                break
            else:
                start = end + 1

s_re = re.compile(r'.*\bss?\.', re.IGNORECASE)

def check_end(text, sentence_start, end, trace):
    # check for space after end:
    if end + 1 != len(text) and not text[end + 1].isspace():
        if trace:
            print(f"check_end {len(text)=}, {end=}: no space after '.', -> False")
        return False

    # check for s_re
    sp = text.rfind(' ', sentence_start, end)
    if trace:
        print(f"check_end {len(text)=}, {sentence_start=}, {end=}: space before '.', {sp=}")
    if sp < end - 3:
        if trace:
            print("space too far away for s_re -> True")
        return True
    if trace:
        print(f"checking {text[sp:sp + 4]!r} for s_re")
    m = s_re.match(text, sp)
    if trace:
        print("space within range of s_re, got", m)
    return not m

word_re = re.compile(r'.*?\b([a-z]+)\b', re.IGNORECASE)

def get_words(text):
    start = 0
    while True:
        m = word_re.match(text, start)
        if not m: return
        w = m.group(1)
        if w not in ('a', 's', 'ss'):
            yield m.start(1), w
        start = m.end() + 1

def is_word(w):
    return w and w.isalpha() and len(w) > 1


def load_words(version):
    ver_obj = models.Version.objects.get(id=version)
    print(f"loading words for {ver_obj.source!r} {version=}")
    if ver_obj.wordrefs_loaded:
        print("ERROR: load_words already run on version", version)
    else:
        for item in models.Item.objects.filter(version_id=version):
            for p in item.paragraph_set.all():
                print(f"paragraph {item.citation}, {p.body_order}")
                index_paragraph(p)
            for t in item.table_set.all():
                print(f"table {item.citation}, {t.body_order}")
                for c in t.tablecell_set.all():
                    index_cell(c)
        ver_obj.wordrefs_loaded = True
        ver_obj.save()


@transaction.atomic
def run(*args):
    global words
    words = {}
    if 'help' in args:
        print("load_words help:")
        print("  python manage.py runscript load_words")
        print("    loads opp_wordref from all words in latest versions of 719, 61B and GG")
        print("  python manage.py runscript load_words --script-args 719|61b|gg")
        print("    loads opp_wordref from all words in latest versions of 719, 61B or GG")
        print("  python manage.py runscript load_words --script-args 'version' version_id")
        print("    loads opp_wordref from all words in indicated version")
        print("  python manage.py runscript load_words --script-args test")
        print("    runs test on get_sentences function")
        print("  python manage.py runscript load_words --script-args help")
        print("    prints this help message")
    elif 'test' in args:
        p = 'All notices of intended conversion given subsequent to the effective date of this part shall be subject to the requirements of ss. 719.606, 719.608, and 719.61. Tenants given such notices shall have a right of first refusal as provided by s. 719.612.'
        for s_offset, s in get_sentences(p):
            print(s_offset, len(s), repr(s))
            for w_offset, w in get_words(s):
                print("word:", w_offset, s_offset + w_offset, repr(w))
    elif 'version' in args:
        version = int(args[-1])
        load_words(version)
        print_load_synonyms()
        print(f"next: python manage.py runscript load_definitions "
              f"--script-args version {version}")
    elif args:
        source = args[0]
        version = models.Version.latest(Source_map[source])
        load_words(version)
        print_load_synonyms()
        print(f"next: python manage.py runscript load_definitions "
              f"--script-args {source}")
    else:
        for source in Sources:
            version = models.Version.latest(source)
            load_words(version)
        print_load_synonyms()
        print(f"next: python manage.py runscript load_definitions")

def print_load_synonyms():
    print(f"next: python manage.py runscript load_synonyms")
    print("or, if you've already done that:")

