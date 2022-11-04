from django.shortcuts import render

# Create your views here.

from itertools import groupby, chain
from operator import methodcaller, attrgetter, itemgetter

from django.http import HttpResponse
from django.views.decorators.http import require_GET, require_safe
from django.db.models import Q

from operating_procedures import models
from operating_procedures.chunks import chunk



@require_safe
def toc(request):
    r'''Creates a table-of-contents of the 'leg.state.fl.us' Chapter 719 code.

    The context created for the template is a recursive list structure:

        node is [citation, title, [node]]
    '''
    latest_law = models.Version.latest('leg.state.fl.us')
    items = []
    for item in models.Item.objects.filter(version_id=latest_law,
                                           has_title=True).order_by('item_order'):
        title = item.get_title().text

        my_block = item.get_block(with_body=False)
        my_children = my_block.body

        if item.parent_id is None:
            items.append(my_block)
            path = {item.id: my_children}
        else:
            if not path[item.parent_id]:
                path[item.parent_id].append(chunk('items', items=[]))
            path[item.parent_id][0].items.append(my_block)
            path[item.id] = my_children
    blocks = [chunk('items', items=items, body_order=0)]
    #blocks[0].dump()
    return render(request, 'opp/toc.html',
                  context=dict(blocks=blocks))


@require_safe
def cite(request, citation='719'):
    assert citation.startswith('719')
    latest_law = models.Version.latest('leg.state.fl.us')
    citation = citation.replace(' ', '')
    def add_space(cite):
        if '(' in cite:
            i = cite.index('(')
            return cite[:i] + ' ' + cite[i:]
        if '.' in cite:
            return cite + ' '
        return cite + '.'

    if '-' in citation:
        first, last = map(add_space, citation.split('-'))
    else:
        first = add_space(citation)
        last = first

    items = map(methodcaller('get_block'),
                models.Item.objects.filter(version_id=latest_law,
                                           citation__gte=first,
                                           citation__lte=last)
                                   .order_by('item_order'))
    blocks = [chunk('items', items=list(items), body_order=0)]
    blocks[0].dump(depth=10)
    return render(request, 'opp/cite.html',
                  context=dict(citation=citation, blocks=blocks))


@require_safe
def search(request, words):
    words = list(map(methodcaller('lower'), map(methodcaller('strip'), words.split(','))))

    word_groups = list(map(methodcaller('get_synonyms'),
                           models.Word.objects.filter(text__in=words).all()))

    print(f"search got {words=}, {word_groups=}")

    latest_law = models.Version.latest('leg.state.fl.us')

    # list of (para, wordrefs, word_group_index), para repeated for each word_group_index
    para_list1 = [(para, list(wordrefs), word_group_index)
                  for word_group_index, words in enumerate(word_groups)
                  for para, wordrefs
                   in groupby(models.WordRef.objects
                                .select_related('paragraph__item')
                                .filter(
                                   Q(paragraph__item__version_id=latest_law)
                                 | Q(paragraph__cell__table__item__version_id=latest_law),
                                   word_id__in=words)
                                .order_by('paragraph__id'),
                              key=attrgetter('paragraph'))]
    if not para_list1:
        return HttpResponse(f"No results found for {words}.",
                            content_type='text/plain; charset=utf-8')
    print(f"got {len(para_list1)} paragraphs")
    para_list1.sort(key=lambda x: (x[0].item.item_order, x[0].body_order))

    # Store word_group_index in wordref objects as 'info'
    print("para_list1:")
    for para, wordrefs, word_group_index in para_list1:
        print(f"  {para=}, {wordrefs=}, {word_group_index=}")
        for wr in wordrefs:
            wr.info = word_group_index + 1

    # list of (item, item_word_groups, [(para, wordrefs)])
    # sorted by item_order, body_order with no duplicate items or paragraphs.
    wordrefs = []
    for item, paras in groupby(para_list1, key=lambda x: x[0].item):
        item_word_groups = set()
        new_paras = []
        for para, para_wordrefs in groupby(paras, key=itemgetter(0)):
            para_wordrefs = list(para_wordrefs)
            new_paras.append((para, list(chain.from_iterable(map(itemgetter(1),
                                                                 para_wordrefs)))))
            item_word_groups.update(map(itemgetter(2), para_wordrefs))
        wordrefs.append((item, item_word_groups, new_paras))

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
                next_item = item
                children.append((item, item_word_groups, paras))
                while next_item.parent != first_item:
                    children.append((next_item.parent, frozenset(), []))
                    next_item = next_item.parent
                yield from reversed(children)
            else:
                yield item, item_word_groups, paras
                first_item = item

    print(f"connect_items called with {len(wordrefs)} wordrefs")
    for item, item_word_groups, paras in connect_items(wordrefs):
        print(f"  {item=}, {item_word_groups=}, {len(paras)=}")

    def sift(wordrefs, word_groups_seen=frozenset()):
        r'''Nests linear wordrefs structure.

        Also inserts ('omitted', None) paragraphs where one or more paragraphs were skipped.
        '''
        wordrefs = iter(wordrefs)
        tree = []
        first_item, first_item_word_groups, first_paras = next(wordrefs)
        first_item_word_groups.update(word_groups_seen)
        print(f"sift {first_item=}, {first_item_word_groups}, {first_paras=}")
        children = []
        for item, groups, paras in wordrefs:
            if item.citation.startswith(first_item.citation):
                print(f"sift got {item=}, {paras=} -- appending")
                children.append((item, groups, paras))
            else:
                print(f"sift got {item=}, {groups=}, {paras=} -- tying off {children=}")
                if children:
                    first_children = sift(children, first_item_word_groups)
                    children = []
                else:
                    first_children = []
                if len(first_item_word_groups) == len(word_groups) or first_children:
                    print(f"sift appending {first_paras=}, {first_children=} to tree")
                    tree.append((first_item, combine_elements(first_item, first_paras,
                                                              first_children)))
                first_item, first_item_word_groups, first_paras = item, groups, paras
                first_item_word_groups.update(word_groups_seen)
                print(f"switching to {first_item=}, {first_item_word_groups=}, "
                      f"{first_paras=}")
        print(f"sift, no more items, checking last item {first_item=}")
        if children:
            first_children = sift(children, first_item_word_groups)
        else:
            first_children = []
        if len(first_item_word_groups) == len(word_groups) or first_children:
            print(f"sift, appending last item {first_paras=}, {first_children=}")
            tree.append((first_item, combine_elements(first_item, first_paras,
                                                      first_children)))
        print(f"sift returning {tree}")
        return tree

    def combine_elements(parent_item, paras, children):
        r'''Combines paras and children in the proper order.

        Also adds ('omitted', None) paragraphs where paragraphs were skipped in paras.

        paras is sequence of (para, wordrefs)
        children is sequence of (item, [elements])
        '''
        ans = []
        next = 1
        for first, second in sorted(chain(paras, children), key=lambda x: x[0].body_order):
            if first.body_order > next and \
               models.Paragraph.objects.filter(item=parent_item,
                                               body_order__range=(next,
                                                                  first.body_order - 1)) \
                                       .exists():
                ans.append(('omitted', None))
            ans.append((first, second))
            next = first.body_order + 1
        if first.body_order < parent_item.num_elements and \
           models.Paragraph.objects.filter(item=parent_item,
                                           body_order__gt=first.body_order) \
                                   .exists():
            ans.append(('omitted', None))
        return ans

    # list of (item,
    #          [(para, wordrefs) | [tree]]  # sorted by body_order
    #         )
    tree = sift(connect_items(wordrefs))

    if not tree:
        return HttpResponse(f"No results found for {words}.",
                            content_type='text/plain; charset=utf-8')

    #items = map(methodcaller('get_block'),
    #            models.Item.objects.filter(version_id=latest_law,
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
                if item_block.body and isinstance(item_block.body[0], models.Paragraph) and \
                   item_block.body[0].body_order == 0:
                    # Move to title!
                    item_block.title = item_block.body[0]
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

    blocks = prepare_blocks(tree)
    blocks[0].dump(depth=10)
    return render(request, 'opp/search.html',
                  context=dict(words=words, blocks=blocks))
