from django.shortcuts import render

# Create your views here.

from itertools import groupby, chain
from operator import methodcaller, attrgetter, itemgetter

from django.http import HttpResponse
from django.views.decorators.http import require_GET, require_safe
from django.db.models import Q

from operating_procedures import models
from operating_procedures.chunks import chunk, Little_stuff
from operating_procedures.scripts.sources import *


@require_safe
def toc(request, source='719'):
    r'''Creates a table-of-contents of the 'leg.state.fl.us' Chapter 719 code.

    The context created for the template is a list of blocks (see chunks.py).
    '''
    if source in Source_map:
        latest_law = models.Version.latest(Source_map[source])
    else:
        return HttpResponse(f"Invalid source: {source}.",
                            content_type='text/plain; charset=utf-8',
                            status=400)
    print(f"toc {source=} {latest_law=}")
    top_level_items = []
    item_iter = iter(models.Item.objects.filter(version_id=latest_law).order_by('item_order'))
    def get_children_of(parent):
        r'''Returns parent_chunk (or None), next_item (or None)
        '''
        child = next(item_iter, None)
        children = []
        while child is not None and  child.parent == parent:
            item_chunk, child = get_children_of(child)
            if item_chunk is not None:
                children.append(item_chunk)
        if parent.has_title or children:
            my_block = parent.get_block(with_body=False)
            if children:
                my_block.body.append(chunk('items', items=children, body_order=0))
            return my_block, child
        return None, child
    item = next(item_iter, None)
    while item is not None:
        item_chunk, item = get_children_of(item)
        if item_chunk is not None:
            top_level_items.append(item_chunk)
    blocks = [chunk('items', items=top_level_items, body_order=0)]
    #blocks[0].dump(4)
    return render(request, 'opp/toc.html',
                  context=dict(blocks=blocks))


@require_safe
def cite(request, citation='719'):
    if citation.startswith('719') or citation.upper().startswith('PART '):
        latest_law = models.Version.latest(Source_719)
    elif citation.upper().startswith('61B-'):
        latest_law = models.Version.latest(Source_61B)
    elif citation.startswith('GG '):
        latest_law = models.Version.latest(Source_GG)
    else:
        return HttpResponse(f"Unknown citation: {citation}.",
                            content_type='text/plain; charset=utf-8',
                            status=400)

    citation = citation.replace(' ', '')
    def add_space(cite):
        if cite.upper().startswith("GG"):
            cite = cite[:2] + ' ' + cite[2:]
            if cite.upper().startswith("GG ARTICLE"):
                cite = cite[:10] + ' ' + cite[10:]
            return cite
        if cite.upper().startswith('PART'):
            return cite[:4] + ' ' + cite[4:]
        if '(' in cite:
            i = cite.index('(')
            return cite[:i] + ' ' + cite[i:]
        if '.' in cite:
            return cite + ' '
        return cite
    if citation.startswith('61B'):
        start = 4
    else:
        start = 0
    hyphen = citation.find('-', start)
    if hyphen > 0:
        first = add_space(citation[:hyphen])
        last = add_space(citation[hyphen + 1:])
        first_item = models.Item.objects.get(version_id=latest_law, citation=first)
        parent = first_item.parent
        items = [item.get_block(with_references=True, top=True)
                 for item in parent.item__set
                  if first <= item.citation <= last]
    else:
        first = add_space(citation)
        last = first
        items = [models.Item.objects.get(version_id=latest_law, citation=first)
                                    .get_block(with_references=True, top=True)]

    print(f"cite: {first=!r}, {last=!r} {latest_law=} got {len(items)} items")

    if len(items) == 1:
        items[0].alone = True

    blocks = [chunk('items', items=items, body_order=0)]
    #blocks[0].dump(depth=3)
    return render(request, 'opp/cite.html',
                  context=dict(citation=citation, blocks=blocks, little_tags=Little_stuff))


@require_safe
def search(request, words):
    trace = True

    # stripped, lowercase
    words = list(map(methodcaller('lower'),
                     map(methodcaller('strip'), words.split(','))))

    # list of sets of synonyms: [set(word.id)]
    word_groups = list(map(methodcaller('get_synonyms'),
                           models.Word.objects.filter(text__in=words).all()))

    #if trace:
    print(f"search got {words=}, expands to {word_groups=}")

    latest_versions = [models.Version.latest(source) for source in Sources]

    def search_document(latest_version):
        # list of (para, wordrefs, word_group_index), para repeated for each word_group_index
        para_list1 = [(para, list(wordrefs), word_group_index)
                      for word_group_index, words in enumerate(word_groups)
                      for para, wordrefs
                       in groupby(models.WordRef.objects
                                    .select_related('paragraph__item')
                                    .filter(
                                       Q(paragraph__item__version_id=latest_version)
                      ,  # FIX:      | Q(paragraph__cell__table__item__version_id=latest_version),
                                       word_id__in=words)
                                    .order_by('paragraph__id'),
                                  key=attrgetter('paragraph'))]
        if not para_list1:
            return []
        if trace:
            print(f"got {len(para_list1)} paragraphs")
        para_list1.sort(key=lambda x: (x[0].parent_item().item_order, x[0].body_order))

        def check_para_list1():
            if not para_list1:
                return
            last_p = para_list1[0][0]
            for p, wordrefs, word_group_index in para_list1[1:]:
                assert p.parent_item().item_order >= last_p.parent_item().item_order, \
                       f"check_para_list1: ERROR {p.item.item_order=} < {last_p.item.item_order}"
                if p.parent_item().item_order == last_p.parent_item().item_order:
                    assert p.body_order >= last_p.body_order, \
                           f"check_para_list1: ERROR {p.body_order=} < {last_p.body_order}"
                assert wordrefs, f"check_para_list1: {para.text[:20]!r} has no wordrefs " \
                                 f"for {word_group_index=}"
                last_p = p

        check_para_list1()

        # Store word_group_index in wordref objects as 'info'
        if trace:
            print("para_list1:")
        for para, wordrefs, word_group_index in para_list1:
            if trace:
                print(f"  {para=}, {wordrefs=}, {word_group_index=}")
            for wr in wordrefs:
                wr.info = word_group_index + 1

        # list of (item, item_word_groups, [(para, wordrefs)])
        # sorted by item_order, body_order with no duplicate items or paragraphs.
        wordrefs = []
        for item, paras in groupby(para_list1, key=lambda x: x[0].parent_item()):
            #print(f"making wordrefs, next item is {item}, {item.as_str()}")
            item_word_groups = set()
            new_paras = []
            for para, para_wordrefs in groupby(paras, key=itemgetter(0)):
                para_wordrefs = list(para_wordrefs)
                wrs = list(chain.from_iterable(map(itemgetter(1),
                                                   para_wordrefs)))
                assert wrs
                new_paras.append((para, wrs))
                item_word_groups.update(map(itemgetter(2), para_wordrefs))
            assert new_paras
            print(f"adding {item.citation} {item_word_groups=} {len(new_paras)=}")
            wordrefs.append((item, item_word_groups, new_paras))

        def check_wordrefs(wordrefs):
            last_item = wordrefs[0][0]
            def check_paras(item, paras):
                if not paras:
                    return
                last_p = paras[0][0]
                for p, _ in paras[1:]:
                    assert p.id != last_p.id, \
                           f"check_wordrefs: {item.as_str()} ERROR " \
                           f"{p.id=} == {last_p.id}"
                    assert p.body_order > last_p.body_order, \
                           f"check_wordrefs: {item.as_str()} ERROR " \
                           f"{p.id=} {p.body_order=} <= " \
                           f"{last_p.id} {last_p.body_order}"
                    last_p = p
            check_paras(last_item, wordrefs[0][2])
            for item, _, paras in wordrefs[1:]:
                assert item.id != last_item.id, \
                       f"check_wordrefs: {item.as_str()} ERROR " \
                       f"{item.id=} == {last_item.id=}"
                assert item.item_order > last_item.item_order, \
                       f"check_wordrefs: {item.as_str()} ERROR " \
                       f"{item.item_order=} <= {last_item.item_order=}"
                check_paras(item, paras)
                last_item = item

        check_wordrefs(wordrefs)

        if trace and False:
            print("wordrefs:")
            for item, item_word_groups, paras in wordrefs:
                print(f"  {item=}, {item_word_groups=}, {paras=}")

        def connect_items(wordrefs):
            r'''Fills in empty item gaps between grandparent items and grandchild items.

            Generates item, item_word_groups, [para, wordrefs], adding empty items as needed.
            '''
            wordrefs = iter(wordrefs)
            first_item, first_word_groups, first_paras = next(wordrefs)
            yield first_item, first_word_groups, first_paras
            for item, item_word_groups, paras in wordrefs:
                if item.citation.startswith(first_item.citation):
                    assert item.citation != first_item.citation
                    next_item = item
                    children = [(item, item_word_groups, paras)]
                    while next_item.parent != first_item:
                        children.append((next_item.parent, set(), []))
                        next_item = next_item.parent
                    yield from reversed(children)
                else:
                    yield item, item_word_groups, paras
                first_item = item

        check_wordrefs(list(connect_items(wordrefs)))

        if trace:
            print(f"connect_items called with {len(wordrefs)} wordrefs")
            for item, item_word_groups, paras in connect_items(wordrefs):
                print(f"  {item=}, {item_word_groups=}, {len(paras)=}")

        def sift(wordrefs, word_groups_seen=frozenset(), trace=False):
            r'''Nests linear wordrefs structure.

            Also inserts ('omitted', None) paragraphs where one or more paragraphs were skipped.
            '''
            wordrefs = iter(wordrefs)
            tree = []
            first_item, first_item_word_groups, first_paras = next(wordrefs)
            first_item_word_groups.update(word_groups_seen)
            if trace:
                print(f"sift {first_item=}, {first_item_word_groups}, {first_paras=}")
            children = []
            for item, groups, paras in wordrefs:
                if item.citation.startswith(first_item.citation):
                    if trace:
                        print(f"sift got {item=}, {paras=} -- appending")
                    children.append((item, groups, paras))
                else:
                    if trace:
                        print(f"sift got {item=}, {groups=}, {paras=} -- tying off {children=}")
                    if children:
                        first_children = sift(children, first_item_word_groups, trace)
                        children = []
                    else:
                        first_children = []
                    if len(first_item_word_groups) == len(word_groups) or first_children:
                        if trace:
                            print(f"sift appending {first_paras=}, {first_children=} to tree")
                        tree.append((first_item, combine_elements(first_item, first_paras,
                                                                  first_children)))
                    first_item, first_item_word_groups, first_paras = item, groups, paras
                    first_item_word_groups.update(word_groups_seen)
                    if trace:
                        print(f"switching to {first_item=}, {first_item_word_groups=}, "
                              f"{first_paras=}")
            if trace:
                print(f"sift, no more items, checking last item {first_item=}")
            if children:
                first_children = sift(children, first_item_word_groups, trace)
            else:
                first_children = []
            if len(first_item_word_groups) == len(word_groups) or first_children:
                if trace:
                    print(f"sift, appending last item {first_paras=}, {first_children=}")
                tree.append((first_item, combine_elements(first_item, first_paras,
                                                          first_children)))
            if trace:
                print(f"sift returning {tree}")
            return tree

        def combine_elements(parent_item, paras, children):
            r'''Combines paras and children in the proper order.

            Also adds ('omitted', None) paragraphs where paragraphs were skipped in paras.

            paras is sequence of (para, wordrefs)
            children is sequence of (item, [elements])
            '''
            #print(f"combine_elements({parent_item=}, ...)")
            ans = []
            next = 1
            for first, second in sorted(chain(paras, children), key=lambda x: x[0].body_order):
                #print(f"  next element {first=}, {first.body_order=}, {next=}")
                if first.body_order > next and \
                   models.Paragraph.objects.filter(item=parent_item,
                                                   body_order__range=(next,
                                                                      first.body_order - 1)) \
                                           .exists():
                    #print("  appending 'omitted'")
                    ans.append(('omitted', None))
                ans.append((first, second))
                next = first.body_order + 1
            #print(f"  done: {first=}, {first.body_order=}, {parent_item.num_elements=}")
            if first.body_order < parent_item.num_elements and \
               models.Paragraph.objects.filter(item=parent_item,
                                               body_order__gt=first.body_order) \
                                       .exists():
                #print("  appending 'omitted'")
                ans.append(('omitted', None))
            return ans

        # list of (item,
        #          [(para, wordrefs) | [tree]]  # sorted by body_order
        #         )
        tree = sift(connect_items(wordrefs))

        if not tree:
            return []

        #items = map(methodcaller('get_block'),
        #            models.Item.objects.filter(version_id__in=latest_versions,
        #                                       citation__gte=first,
        #                                       citation__lte=last)
        #                               .order_by('item_order'))
        def prepare_blocks(tree):
            r'''Converts tree to a list of chunk blocks.
            '''
            blocks = []
            sub_items = []
            for element in tree:
                if isinstance(element[0], models.Item):
                    item_block = element[0].get_block(with_body=False)
                    item_block.body = prepare_blocks(element[1])

                    # Check for title in item_block.body as body_order == 0.  If found, pull it
                    # out and replace item_block.title with it so that the title has the search
                    # highlights.
                    if item_block.body and item_block.body[0].tag == 'paragraph' and \
                       item_block.body[0].body_order == 0:
                        # Move to title!
                        item_block.title = item_block.body[0].chunks
                        del item_block.body[0]

                    sub_items.append(item_block)
                else:
                    if sub_items:
                        blocks.append(chunk('items',
                                            items=sub_items,
                                            body_order=sub_items[0].body_order))
                        sub_items = None
                    if isinstance(element[0], models.Paragraph):
                        blocks.append(element[0].get_block(wordrefs=element[1]))
                    elif isinstance(element[0], models.Table):
                        blocks.append(element[0].get_block())  # FIX: How should this work?
                    elif element[0] == 'omitted':
                        blocks.append(chunk('omitted')) 
            if sub_items:
                blocks.append(chunk('items',
                                    items=sub_items,
                                    body_order=sub_items[0].body_order))
            return blocks

        return prepare_blocks(tree)

    blocks = []
    for latest_version in latest_versions:
        blocks.extend(search_document(latest_version))

    if not blocks:
        return HttpResponse(f"No results found for {words}.",
                            content_type='text/plain; charset=utf-8')

    #blocks[0].dump(depth=10)
    return render(request, 'opp/search.html',
                  context=dict(words=words, blocks=blocks, little_tags=Little_stuff))


def synonyms(request, word):
    w = models.Word.objects.get(text=word)
    syns = sorted(models.Word.get_text(syn) for syn in w.get_synonyms())
    return render(request, 'opp/synonyms.html',
                  context=dict(word=w.text, syns=syns))


def versions(request):
    versions = models.Version.objects.order_by('-upload_date').all()
    return render(request, 'opp/versions.html',
                  context=dict(versions=versions))


def item_debug(request, version_id, citation=None):
    if citation is None:
        item = models.Item.objects.get(id=version_id)
        version_id = item.version_id
    else:
        try:
            item = models.Item.objects.get(version_id=version_id, citation=citation)
        except models.Item.DoesNotExist:
            item = None
    if item is not None:
        return render(request, 'opp/item_debug.html',
                      context=dict(item=item,
                        paragraphs=models.Paragraph.objects.filter(item_id=item.id).all(),
                        tables=models.Table.objects.filter(item_id=item.id).all(),
                        subitems=models.Item.objects.filter(parent_id=item.id)
                                                    .order_by('body_order').all()))
    return render(request, 'opp/item_debug.html',
                  context=dict(
                    version_id=version_id,
                    item=None,
                    paragraphs=[],
                    tables=[],
                    subitems=models.Item.objects.filter(version_id=version_id,
                                                        citation__startswith=citation)
                                                .order_by('item_order').all()))


def paragraph_debug(request, paragraph_id):
    paragraph = models.Paragraph.objects.get(id=paragraph_id)
    annotations = models.Annotation.objects.filter(paragraph_id=paragraph.id) \
                                           .order_by('char_offset', 'length') \
                                           .all()
    for anno in annotations:
        anno.text = paragraph.text[anno.char_offset: anno.char_offset + anno.length]
    return render(request, 'opp/paragraph_debug.html',
                  context=dict(
                    paragraph=paragraph,
                    annotations=annotations))
