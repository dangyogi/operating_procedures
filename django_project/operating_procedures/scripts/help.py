# help.py

import os
from glob import iglob


dir = os.path.dirname(__file__)

def run():
    print("scripts:")
    for path in sorted(iglob(os.path.join(dir, '*.py'))):
        script = os.path.basename(path)[:-3]
        if not script.startswith("__"):
            print("  ", script, sep='')
