# load_synonyms.py

from pathlib import Path

from django.db import transaction

from operating_procedures import models


Synonyms_file = Path(__file__).parents[2] / 'synonyms.txt'


def load_synonyms(synonyms_file):
    with open(synonyms_file, 'r') as synonyms:
        for line in synonyms:
            line = line.strip()
            if line and line[0] != '#':
                words = list(map(models.Word.lookup_word, line.split()))
                first = words[0]
                for second in words[1:]:
                    models.Synonym.add_synonym(first.id, second.id)


@transaction.atomic
def run(*args):
    if 'help' in args:
        print("load_synonyms help:")
        print("  manage.py runscript load_synonyms")
        print("    loads synonyms from synonyms.txt")
        print("  manage.py runscript load_synonyms --script-args synonyms_file")
        print("    loads synonyms from synonyms_file")
        print("  manage.py runscript load_synonyms --script-args test word")
        print("    shows synonyms for word")
        print("  manage.py runscript load_synonyms --script-args help")
        print("    prints this help message")
    elif 'test' in args:
        word = models.Word.lookup_word(args[1])
        print(f"{word.text}({word.id}) has", 
              [f"{models.Word.get_text(id)}({id})" for id in word.get_synonyms()])
    elif args:
        synonyms_file = args[0]
        load_synonyms(synonyms_file)
    else:
        load_synonyms(Synonyms_file)
        print(f"next: python manage.py runscript load_definitions")
