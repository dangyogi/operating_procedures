# load_definitions.py

from itertools import chain
import re

from django.db import transaction
from django.db.models import Q

from operating_procedures import models


term_re = re.compile(r'''
    ["\u201c][^"\u201d]+["\u201d]
    (?: \ +or \ +
        ["\u201c][^"\u201d]+["\u201d])*
''', re.VERBOSE)

or_re = re.compile(r' +or +')

def annotate(version, definition):
    print("processing", definition.citation)
    def_text = definition.paragraph_set.get(body_order=1).text
    assert def_text[0] in ('"', '\u201c'), \
           f'Expected ", got {ord(def_text[0])} {ord(def_text[11])}'
    terms_text = term_re.match(def_text).group()
    #print(f"{terms_text=}")
    terms = or_re.split(terms_text)
    #print(f"{terms=}")
    for term in terms:
        annotate_term(version, definition.citation, term[1:-1].split())

def annotate_term(version, definition_citation, words):
    print(f"annotate_term {version=} {definition_citation=} {words=}")
    w = words[0]
    first_words = [models.Word.objects.get(id=id)
                   for id in models.Word.lookup_word(w).get_synonyms()]
    rest_words = words[1:]

    for ref in chain.from_iterable(
                 chain(word.wordref_set.filter(
                         paragraph__item__version=version).all(),
                       word.wordref_set.filter(
                         paragraph__cell__table__item__version=version).all())
                 for word in first_words):
        char_offset = ref.char_offset
        for w in rest_words:
            try:
                ref = ref.get_next_word()
            except models.WordRef.DoesNotExist:
                # nope!
                #print(w, "not found, not enough words in sentence")
                break
            if ref.word_id not in models.Word.lookup_word(w).get_synonyms():
                # nope!
                #print(w, models.Word.lookup_word(w).get_synonyms(),
                #      "not found, next word was",
                #      models.Word.get_text(ref.word_id))
                break
        else:
            print(f"creating annotation paragraph_id={ref.paragraph_id} {char_offset=} "
                  f"length={ref.char_offset + ref.length - char_offset}")
            models.Annotation(paragraph_id=ref.paragraph_id, type="definition",
                              char_offset=char_offset,
                              length=ref.char_offset + ref.length - char_offset,
                              info=definition_citation).save()

def get_synonyms(word):
    return [word]

@transaction.atomic
def run(*args):
    if 'help' in args:
        print("load_definitions help:")
        print("  manage.py runscript load_definitions --script-args help")
        print("    prints this help message")
        #print("  manage.py runscript load_definitions --script-args test")
        #print("    runs test on get_sentences function")
        print("  manage.py runscript load_definitions")
        print("    loads opp_annotations for all definition references in "
              "latest version of chapter 719")
        print("  manage.py runscript load_definitions --script-args version_id")
        print("    loads opp_annotations for all definition references in "
              "indicated version of chapter 719")
    elif 'test' in args:
        pass
    else:
        if args:
            version = int(args[0])
        else:
            version = models.Version.latest('leg.state.fl.us')
            print("loading version", version)
        ver_obj = models.Version.objects.get(id=version)
        if ver_obj.definitions_loaded:
            print("ERROR: load_definitions already run on version", version)
        elif ver_obj.source == 'leg.state.fl.us':
            definitions = models.Item.objects.get(version_id=version, has_title=True,
                                                  paragraph__body_order=0,
                                                  paragraph__text='Definitions.')
            fac_version = models.Version.latest('casetext.com')
            print(f"doing definitions from {definitions.citation} to "
                  f"{version=} and {fac_version=}")
            for definition in definitions.item_set.all():
                annotate(version, definition)
                annotate(fac_version, definition)
            ver_obj.definitions_loaded = True
            ver_obj.save()
        else:
            assert ver_obj.source == 'casetext.com'
            for definitions in models.Item.objects.filter(Q(paragraph__text='Definitions.')
                                                          | Q(paragraph__text='Definition.'),
                                                          version_id=version, has_title=True,
                                                          paragraph__body_order=0):
                base_citation = definitions.parent.citation
                print(f"doing definitions from {definitions.citation} to "
                      f"{version=} {base_citation=}")
                #for definition in definitions.item_set.all():
                #    annotate(version, definition)
            #ver_obj.definitions_loaded = True
            #ver_obj.save()
        print("next: python manage.py runscript show_outline")
