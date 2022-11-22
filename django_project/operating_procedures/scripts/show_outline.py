# show_outline.py

from operating_procedures import models
from operating_procedures.scripts.sources import *


def run(*args):
    if 'help' in args:
        print("show_outline help:")
        print("  python manage.py runscript show_outline")
        print("    Prints outline for latest version of chapter 719.")
        print("  python manage.py runscript show_outline --script-args source")
        print("    Prints outline for latest version of source.")
        print("  python manage.py runscript show_outline --script-args version version_id")
        print("    Prints outline for specified version.")
        print("  python manage.py runscript show_outline --script-args help")
        print("    Prints this help message.")
    else:
        if 'version' in args:
            version = int(args[args.index('version') + 1])
        elif args:
            version = models.Version.latest(Source_map[args[0]])
        else:
            version = models.Version.latest(Source_719)
        path = []

        def print_item(item):
            if item.parent_id is None:
                number = item.citation
            else:
                number = item.number
            if item.has_title:
                print(f"{'  ' * len(path)}{number}: {item.get_title().text}")
            else:
                print(f"{'  ' * len(path)}{number}:")

        def adjust_path_and_print(item):
            nonlocal path
            if item.parent_id is None:
                path = []
                print_item(item)
                path.append(item.id)
            elif item.parent_id not in path:
                adjust_path_and_print(item.parent)
                print_item(item)
                path.append(item.id)
            else:
                i = path.index(item.parent_id)
                del path[i + 1:]
                print_item(item)
                path.append(item.id)

        for item in models.Item.objects.filter(version_id=version,
                                               has_title=True).order_by('item_order'):
            adjust_path_and_print(item)

