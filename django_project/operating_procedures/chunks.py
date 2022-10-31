# chunks.py

r'''This defines the interface between the view and the template for textual data.

The view produces a set of nested chunk objects, each with a 'tag' identifying what type
of chunk it is, and a set of attributes.  These contain no html.

The template translates these into html as it sees fit.

Tags for text chunks (aka "text-chunks" in this description):
    'text': text<string>
    'cite': citation<string> (which might be a hyphenated range), url<string>
            chunks<[text-chunk]>
    'note': term<[text-chunk]>, note<string>
    'definition': term<[text-chunk]>, definition<[block]> (definition could have items)

Tags for larger blocks of text:
    'items': items<[item]>
             body_order<int>
    'paragraph': chunks<[text-chunk]>
                 body_order<int>
    'table': has_header<bool>
             rows<[[[block]]]>  # list of rows,
                                # each row a list of columns,
                                # each column a list of blocks (no items here!).
             body_order

And finally the item itself!  (only appears in 'items' chunk)
    'item': citation<string>
            number<string>
            url<string>
            title<[text-chunk]> (may be None),
            history<string> (may be None),
            notes<[(number, string)]>
            body<[block]> (could have items)
            body_order<int>
'''

from itertools import groupby
from operator import attrgetter

from django.urls import reverse


class chunk:
    r'''These represent strings of text, as well as larger blocks of text.

    The strings may include possibly nested annotations.

    The blocks of text may be arranged hierarchically.
    '''
    def __init__(self, tag, **attrs):
        self.tag = tag
        for name, value in attrs.items():
            setattr(self, name, value)


def chunkify_text(parent_item, text, annotations, start=0, end=None):
    r'''Returns a list of text-chunks.
    '''
    if end is None:
        end = len(text)
    ans = []

    def make_annotation(my_annotations):
        nonlocal annotations
        nested_annotations = []
        my_annotation = my_annotations[0]

        # local start, end
        start = my_annotation.char_offset
        end = start + my_annotation.length

        for i, annotation in enumerate(my_annotations):
            if annotation.char_offset >= end:
                break
            if annotation.char_offset + annotation.length <= end:
                nested_annotations.append(annotation)
            else:
                # This annotation overlaps the first annotation.  We cut the first
                # annotation short in this case...
                end = annotation.char_offset

                # removed nested_annotations after the cutoff (in reverse order)
                while nested_annotations[-1].char_offset >= end:
                    del nested_annotations[-1]
        ans.extend(make_chunk(parent_item, my_annotation,
                              chunkify_text(parent_item, text, nested_annotations,
                                            start, end)))
        del annotations[0: len(nested_annotations) + 1]
        return end  # this will be the new start in text

    while start < len(text):
        if not annotations:
            ans.append(chunk('text', text=text[start:]))
            break
        assert annotations[0].char_offset >= start
        if annotations[0].char_offset > start:
            ans.append(chunk('text', text=text[start: annotations[0].char_offset]))
        start = make_annotation(annotations)  # includes nested annotations
    assert not annotations
    return ans


fl_leg_url_prefix = \
  f"http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL="

def make_fl_leg_url(citation):
    if '(' in citation:
        citation = citation.split('(')[0]
    if '.' in citation:
        chapter, section = citation.split('.')
    else:
        chapter, section = citation, None
    hundreds_start = chapter - chapter % 100
    url_start = f"{fl_leg_url_prefix}{hundreds_start:04d}-{hundreds_start + 99:04d}/" \
                f"{hundreds_start}/{chapter:04d}/"
    if section is None:
        return f"{url_start}{chapter:04d}.html"
    return f"{url_start}Sections/{chapter:04d}.{section:02d}.html"


def make_chunk(parent_item, annotation, text_chunks):
    r'''Called by chunkify_text.
    '''
    if annotation.tag == 's_link':
        citation = annotation.info
        if citation.startswith('719'):
            url = reverse('cite', citation=citation)
        elif '-' in citation:
            print("WARNING: Could not make url for '-' in citation:", citation)
            return text_chunks
        else:
            url = make_fl_leg_url(citation)
        return [chunk('cite', citation=citation, url=url, chunks=text_chunks)]
    if annotation.tag == 'note':
        return [chunk('note', note=parent_item.get_note(annotation.info), term=text_chunks)]
    elif annotation.tag == 'definition':
        return [chunk('definition', term=text_chunks,
                      definition=chunkify_item_body(
                                   models.Item.objects.get(citation=annotation.info)))]
    else:
        raise AssertionError(f"Unknown annotation type {annotation.type!r}")


def chunk_item(item, with_body=True):
    ans = chunk(tag='item',
                citation=item.citation,
                number=item.number,
                title=None,
                history=item.history,
                notes=[],
                url=reverse('cite', citation=item.citation),
                body=[],
                body_order=item.body_order)
    if item.has_title:
        ans.title = item.get_title().with_annotations()
    for note in item.note_set.all():
        ans.notes.append((note.number, note.text))
    if with_body:
        ans.body = chunkify_item_body(item)
    return ans


def chunkify_item_body(item):
    r'''Returns a list of blocks.
    '''
    ans = sorted(map(get_block, item.get_body()), key=attrgetter('body_order'))

    # put all children (if any) into a single 'items' chunk:
    for i, block in enumerate(ans):
        if block.tag == 'item':
            children = []
            for j in range(i, len(ans)):
                if ans[j].tag != 'item':
                    break
                children.append(ans[j])
            else:
                assert not children
                break
            assert children
            ans[i: i + len(children)] = [chunk('items', items=children,
                                               body_order=children[0].body_order)]
            break

    return ans


def get_block(obj):
    return obj.get_block()


def chunk_paragraph(paragraph):
    return chunk('paragraph', chunks=paragraph.with_annotations(),
                 body_order=paragraph.body_order)


def chunk_table(table):
    ans = chunk('table', has_header=table.has_header, rows=[], body_order=table.body_order)
    for row, cells in groupby(table.tablecell_set.all(), key=attrgetter('row')):
        ans.rows.append(list(map(get_blocks, cells)))
    return ans

