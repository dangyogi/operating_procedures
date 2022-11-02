from django.shortcuts import render

# Create your views here.

from operator import methodcaller

from django.http import HttpResponse
from django.views.decorators.http import require_GET, require_safe

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
