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
                    words_in_line = line.split()
                    if words_in_line:
                        first = models.Word.lookup_word(words_in_line[0])
                        for w in words_in_line[1:]:
                            second = models.Word.lookup_word(w)
                            models.Synonym(word=first, synonym=second).save()
                            models.Synonym(word=second, synonym=first).save()
        print(f"next: python manage.py runscript load_definitions --script-args <version>")
