from django.shortcuts import render

# Create your views here.

from django.http import HttpResponse
from django.views.decorators.http import require_GET, require_safe

from operating_procedures import models



@require_safe
def toc(request):
    r'''Creates a table-of-contents of the 'leg.state.fl.us' Chapter 719 code.

    The context created for the template is a recursive list structure:

        node is [citation, title, [node]]
    '''
    latest_law = models.Version.latest('leg.state.fl.us')
    blocks = []
    for item in models.Item.objects.filter(version_id=latest_law,
                                           has_title=True).order_by('item_order'):
        title = item.get_title().text

        my_block = item.get_block(with_body=False)
        my_children = my_block.body

        if item.parent_id is None:
            blocks.append(my_block)
            path = {item.id: my_children}
        else:
            path[item.parent_id].append(my_block)
            path[item.id] = my_children
    return render(request, 'opp/toc.html', context={'blocks': blocks})


@require_safe
def cite(request, citation='719'):
    assert citation.startswith('719')
    latest_law = models.Version.latest('leg.state.fl.us')
    path = []
    lines = []
    for item in models.Item.objects.filter(version_id=latest_law,
                                           title__isnull=False).order_by('item_order'):
        if item.parent_id is None:
            path = [item.id]
        else:
            i = path.index(item.parent_id)
            path[i + 1:] = [item.id]
        if item.citation.startswith('PART'):
            citation = item.citation
        else:
            citation = item.citation.replace(' ', '')
        lines.append(f"{' ' * (len(path) - 1)}{citation}: {item.title}")
