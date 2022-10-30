# versions.py

from operating_procedures import models


def run(*args):
    if 'help' in args:
        print("versions help:")
        print("  manage.py runscript versions --script-args help")
        print("    prints this help message")
        print("  manage.py runscript versions")
        print("    prints all version information")
    else:
        for version in models.Version.objects.order_by('-upload_date').all():
            print(f"version {version.id} on {version.upload_date} from {version.source}")

