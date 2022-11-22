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

    print()
    print("order:")
    print("  python manage.py runscript scrape_html --script-args 719")
    print("  python manage.py runscript scrape_html --script-args 61b")
    print("  python manage.py runscript scrape_bylaws")
    print("  python manage.py runscript load_words")
    print("  python manage.py runscript load_synonyms")
    print("  python manage.py runscript load_definitions")
    print("  python manage.py runscript show_outline")
    print("  python manage.py runscript show_outline --script-args 61b")
    print("  python manage.py runscript show_outline --script-args gg")
    print()
    print("run doctests in scrape_html:")
    print("  python manage.py test operating_procedures.scripts.run_doctests")
    print("  (see scripts/run_doctests.py)")
    print()
    print("database sizes:")
    print("  db.sqlite3 ends up at 6.6MB")
    print()
    print("  Table      : #Rows")
    print("  Version    :     3")
    print("  Item       :  1537")
    print("  Paragraph  :  3488")
    print("  Annotation :  6340")
    print("  Table      :     9")
    print("  TableCell  :  1463")
    print("  Word       :  3547")
    print("  Synonym    :  5856")
    print("  WordRef    : 75218")
