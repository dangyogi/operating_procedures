# load_synonyms.py

from django.db import transaction

from operating_procedures import models


@transaction.atomic
def run(*args):
    global words, new_words
    words = {}
    new_words = 0
    if not args or 'help' in args:
        print("load_synonyms help:")
        print("  manage.py runscript load_synonyms --script-args help")
        print("    prints this help message")
        #print("  manage.py runscript load_synonyms --script-args test word")
        #print("    runs test on get_sentences function")
        print("  manage.py runscript load_synonyms --script-args synonym_file")
        print("    loads opp_annotations for all definition references in chapter 719")
    elif 'test' in args:
        word = models.Word.lookup_word(args[1])
        print(f"{word.text}({word.id}) has", 
              [f"{models.Word.get_text(id)}({id})"
               for id in models.Word.lookup_word('voting').get_synonyms()])
    else:
        synonym_file = args[0]
        with open(synonym_file, 'r') as synonyms:
            for line in synonyms:
                line = line.strip()
                if line and line[0] != '#':
                    words = list(map(models.Word.lookup_word, line.split()))
                    first = words[0]
                    for second in words[1:]:
                        models.Synonym.add_synonym(first.id, second.id)
        print(f"next: python manage.py runscript load_definitions --script-args <version>")
