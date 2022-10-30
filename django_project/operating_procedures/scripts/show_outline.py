# show_outline.py

from operating_procedures import models


def run(*args):
    if 'help' in args:
        print("show_outline help:")
        print("  manage.py runscript show_outline --script-args help")
        print("    prints this help message")
        print("  manage.py runscript show_outline")
        print("    prints outline for latest version of chapter 719")
        print("  manage.py runscript show_outline --script-args version_id")
        print("    prints outline for specified version of chapter 719")
    else:
        if args:
            version = int(args[0])
        else:
            version = models.Version.latest('leg.state.fl.us')
        path = []
        for item in models.Item.objects.filter(version_id=version,
                                               has_title=True).order_by('item_order'):
            if item.parent_id is None:
                path = [item.id]
            else:
                i = path.index(item.parent_id)
                path[i + 1:] = [item.id]
            print(f"{'  ' * (len(path) - 1)}{item.number}: {item.get_title().text}")

