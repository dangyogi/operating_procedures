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
    'definition_link': term<[text-chunk]>, link=<url>
    'search_term': term<text-chunk>, word_group_number<int>

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
    'omitted': <no attrs>

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
from operator import attrgetter, methodcaller

from django.urls import reverse
from operating_procedures import models


class chunk:
    r'''These represent strings of text, as well as larger blocks of text.

    The strings may include possibly nested annotations.

    The blocks of text may be arranged hierarchically.
    '''
    def __init__(self, tag, **attrs):
        self.tag = tag
        for name, value in attrs.items():
            setattr(self, name, value)
        self._attrs = attrs
        if tag == 'item' and self.body and self.body[0].tag == 'item':
            assert False
        if False:
            if tag == 'text':
                print(f"chunk('text', text={attrs['text'][:25]!r})")
            else:
                print(f"chunk({tag!r}", end='')
                for name, value in attrs.items():
                    if hasattr(value, 'as_str'):
                        print(f", {name}={value.as_str()}", end='')
                    else:
                        print(f", {name}={value!r}", end='')
                print(")")

    def __repr__(self):
        return f"<chunk {self.tag}>"

    def dump(self, depth=3, indent=0):
        print(f"{' ' * indent}{self.tag}: ", end='')
        sep = ''
        for a in self._attrs:
            value = getattr(self, a)
            if isinstance(value, str):
                if len(value) > 35:
                    value_str = f"{value[:25]}...{value[-10:]}"
                else:
                    value_str = value
                print(f"{sep}{a}='{value_str}'", end='')
                sep = ', '
            elif value is None or isinstance(value, (int, float, tuple)) or not value:
                print(f"{sep}{a}={value!r}", end='')
                sep = ', '
            else:
                assert isinstance(value, list), \
                       f"dump: expected list in {self.tag}.{a}, got {value!r}"
        print()
        if depth > 0:
            for a in self._attrs:
                value = getattr(self, a)
                if isinstance(value, list) and value:
                    print(f"{' ' * indent}  {a}=[")
                    for x in value:
                        if isinstance(x, chunk):
                            x.dump(depth - 1, indent + 4)
                        else:
                            print(f"{' ' * (indent + 4)}{x}")
                    print(f"{' ' * indent}  ]")


ct_depth = -1

def chunkify_text(parent_item, text, annotations, start=0, end=None, def_as_link=False,
                  trace=False):
    r'''Returns a list of text-chunks.
    '''
    global ct_depth
    ct_depth += 1
    try:
        annotations = list(annotations)
        if trace:
            print(f"{' ' * 2 * ct_depth}>chunkify_text({ct_depth=}, {parent_item=}, "
                  f"text={text[:25]}, {annotations=}, {start=}, {end=})")
        if end is None:
            end = len(text)
        ans = []

        def make_annotation(my_annotations, trace=False):
            nonlocal annotations
            my_annotation = my_annotations[0]

            my_start = my_annotation.char_offset
            my_end = my_start + my_annotation.length
            assert my_end <= end

            if my_annotation.type == 'definition' and \
               my_annotation.info == parent_item.citation:
                del annotations[0]
                if trace:
                    print(f"{' ' * 2 * ct_depth}!make_annotation: "
                          f"parent_item={parent_item.as_str()} {my_annotation=} "
                          f"points to itself")
                if trace:
                    print(f"{' ' * 2 * ct_depth}...make_annotation: returning {my_start}")
                return my_start

            if trace:
                print(f"{' ' * 2 * ct_depth}>make_annotation(len={len(my_annotations)}, "
                      f"{my_start=}, {my_end=}, {my_annotations=})")
            nested_annotations = []

            for i, annotation in enumerate(my_annotations[1:]):
                if annotation.char_offset >= my_end:
                    break
                if annotation.char_offset + annotation.length <= my_end:
                    nested_annotations.append(annotation)
                else:
                    # This annotation overlaps the first annotation.  We cut the first
                    # annotation short in this case...
                    my_end = annotation.char_offset

                    # removed nested_annotations after the cutoff (in reverse order)
                    while nested_annotations and \
                          nested_annotations[-1].char_offset >= my_end:
                        del nested_annotations[-1]
            if my_start < my_end:
                ans.extend(make_chunk(parent_item, my_annotation,
                                      chunkify_text(parent_item, text, nested_annotations,
                                                    my_start, my_end,
                                                    def_as_link=def_as_link),
                                      def_as_link=def_as_link))
            del annotations[0: len(nested_annotations) + 1]
            if trace:
                print(f"{' ' * 2 * ct_depth}<make_annotations: {annotations=} "
                      f"returning {my_end}")
            return my_end  # this will be the new start in text

        while start < end:
            if not annotations:
                ans.append(chunk('text', text=text[start: end]))
                if trace:
                    print(f"{' ' * 2 * ct_depth}<chunkify_text: no more annotations -> {ans}")
                break
            assert annotations[0].char_offset >= start
            if annotations[0].char_offset > start:
                ans.append(chunk('text', text=text[start: annotations[0].char_offset]))
            start = make_annotation(annotations)  # includes nested annotations
        else:
            # This never seems to get hit... ??
            if trace:
                print(f"{' ' * 2 * ct_depth}<chunkify_text: end of text -> {ans}")
        assert not annotations
    except Exception:
        ct_depth -= 1
        raise
    ct_depth -= 1
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
    chapter = int(chapter)
    hundreds_start = chapter - chapter % 100
    url_start = f"{fl_leg_url_prefix}{hundreds_start:04d}-{hundreds_start + 99:04d}/" \
                f"{chapter:04d}/"
    #print(f"make_fl_leg_url({citation}): {chapter=}, {hundreds_start=}, {url_start=}")
    if section is None:
        return f"{url_start}{chapter:04d}.html"
    return f"{url_start}Sections/{chapter:04d}.{int(section):02d}.html"


def make_chunk(parent_item, annotation, text_chunks, def_as_link=False):
    r'''Called by chunkify_text.
    '''
    #print(f"make_chunk({parent_item.as_str()}, {annotation.as_str()}, {text_chunks})")
    if annotation.type == 's_cite':
        citation = annotation.info
        if citation.startswith('719'):
            url = reverse('cite', args=[citation])
        elif '-' in citation:
            print("WARNING: Could not make url for '-' in citation:", citation)
            return text_chunks
        else:
            url = make_fl_leg_url(citation)
        return [chunk('cite', citation=citation, url=url, chunks=text_chunks)]
    if annotation.type == 'note':
        return [chunk('note',
                      note=parent_item.get_note(annotation.info),
                      term=text_chunks)]
    elif annotation.type == 'definition':
        if def_as_link:
            return [chunk('definition_link', term=text_chunks,
                          link=reverse('cite', args=[annotation.info]))]
        else:
            return [chunk('definition', term=text_chunks,
                          # FIX: getting definition, calling chunkify_item_body
                          definition=chunkify_item_body(
                                       models.Item.objects.get(citation=annotation.info),
                                       def_as_link=True))]
    elif annotation.type == 'search_highlight':
        return [chunk('search_term', term=text_chunks, word_group_number=annotation.info)]
    else:
        raise AssertionError(f"Unknown annotation type {annotation.type!r}")


def chunk_item(item, with_body=True, def_as_link=False):
    #print(f"chunk_item({item.as_str()}, {with_body=}, {def_as_link=})")
    ans = chunk('item',
                citation=item.citation,
                number=item.number,
                title=None,
                history=item.history,
                notes=[],
                url=reverse('cite', args=[item.citation]),
                body=[],
                body_order=item.body_order)
    if item.has_title:
        ans.title = item.get_title().with_annotations()
    if item.parent_id is None or item.parent.citation.startswith('PART '):
        ans.parent_citation = None
        ans.parent_url = reverse('toc')
    else:
        ans.parent_citation = item.parent.citation
        ans.parent_url = reverse('cite', args=[item.parent.citation])
    if with_body:
        ans.body = chunkify_item_body(item, def_as_link=def_as_link)
        for note in item.note_set.all():
            ans.notes.append((note.number, note.text))
    else:
        ans.history = None
    return ans


def chunkify_item_body(item, def_as_link=False):
    r'''Returns a list of blocks.
    '''
    #print(f"chunkify_item_body({item.as_str()}, {def_as_link=})")
    items = sorted(map(methodcaller('get_block', def_as_link=def_as_link), item.get_body()),
                   key=attrgetter('body_order'))
    #print(f"chunkify_item_body: body is {items})")

    # put all children (if any) into a single 'items' chunk:
    children = []
    ans = []
    state = 'before_children'

    def check_children():
        nonlocal state
        if state == 'doing_children':
            #print(f"chunkify_item_body: found {len(children)} items")
            ans.append(chunk('items', items=children,
                             body_order=children[0].body_order))
            state = 'after_children'

    for block in items:
        if block.tag == 'item':
            assert state != 'after_children', \
                   f"chunkify_item_body({item=}): got non-item {ans[-1]} " \
                   f"between subordinate items {children[-1]} and {block}"
            children.append(block)
            state = 'doing_children'
        else:
            check_children()
            ans.append(block)

    check_children()
    #print(f"chunkify_item_body: returning {ans}")
    return ans


def chunk_paragraph(paragraph, wordrefs=(), def_as_link=False):
    return chunk('paragraph', chunks=paragraph.with_annotations(wordrefs=wordrefs,
                                                                def_as_link=def_as_link),
                 body_order=paragraph.body_order)


def chunk_table(table, def_as_link=False):
    ans = chunk('table', has_header=table.has_header, rows=[], body_order=table.body_order)
    for row, cells in groupby(table.tablecell_set.all(), key=attrgetter('row')):
        ans.rows.append(list(map(methodcaller('get_blocks', def_as_link=def_as_link),
                                 cells)))
    return ans

