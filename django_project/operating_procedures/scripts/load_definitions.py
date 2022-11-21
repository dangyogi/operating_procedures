# load_definitions.py

from itertools import chain
import re

from django.db import transaction
from django.db.models import Q

from operating_procedures import models
from operating_procedures.scripts.sources import *


term_re = re.compile(r'''
    ["\u201c][^"\u201d]+["\u201d]
    (?: \ +or \ +
        ["\u201c][^"\u201d]+["\u201d])*
''', re.VERBOSE)

or_re = re.compile(r' +or +')

def annotate(anno_version, definition, base_citation=None):
    print(f"annotate: {definition.citation} id={definition.id}")
    def_text = definition.paragraph_set.get(body_order=1).text
    assert def_text[0] in ('"', '\u201c'), \
           f'Expected ", got {ord(def_text[0])=} {ord(def_text[11])=}'
    terms_text = term_re.match(def_text).group()
    print(f"  {terms_text=}")
    terms = or_re.split(terms_text)
    print(f"  {terms=}")
    for term in terms:
        annotate_term(anno_version, definition.citation, term[1:-1].split(), base_citation)

def annotate_term(anno_version, definition_citation, words, base_citation):
    print(f"annotate_term {anno_version=} {definition_citation=} {words=} {base_citation=}")
    w = words[0]
    first_words = [models.Word.objects.get(id=id)
                   for id in models.Word.lookup_word(w).get_synonyms()]
    rest_words = words[1:]

    def get_wordrefs(word):
        if base_citation is None:
            return chain(word.wordref_set.filter(
                           paragraph__item__version=anno_version).all(),
                         word.wordref_set.filter(
                           paragraph__cell__table__item__version=anno_version).all())
        return chain(word.wordref_set.filter(
                       paragraph__item__version=anno_version,
                       paragraph__item__citation__startswith=base_citation).all(),
                     word.wordref_set.filter(
                       paragraph__cell__table__item__version=anno_version,
                       paragraph__cell__table__item__citation__startswith=base_citation).all())

    for ref in chain.from_iterable(get_wordrefs(word) for word in first_words):
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


def load_definitions(def_version, anno_versions):
    def_ver_obj = models.Version.objects.get(id=def_version)
    if def_ver_obj.definitions_loaded:
        print("ERROR: load_definitions already run on version", version)

    for definitions in models.Item.objects.filter(Q(paragraph__text='Definitions.')
                                                  | Q(paragraph__text='Definition.')
                                                  | Q(paragraph__text='Definitions')
                                                  | Q(paragraph__text='Definition'),
                                                  version_id=def_version, has_title=True,
                                                  paragraph__body_order=0):
        if def_ver_obj.source == Source_61B:
            base_citation = definitions.citation[: definitions.citation.index('.')]
        else:
            base_citation = None
        print(f"doing definitions from {definitions.citation} id={definitions.id} to "
              f"{anno_versions=} {base_citation=}")
        if definitions.item_set.exists():
            print(f"item_set exists")
            for definition in definitions.item_set.all():
                for anno_version in anno_versions:
                    annotate(anno_version, definition, base_citation)
        else:
            print(f"item_set empty")
            for anno_version in anno_versions:
                annotate(anno_version, definitions, base_citation)
    def_ver_obj.definitions_loaded = True
    def_ver_obj.save()


Def_sources = Source_719, Source_61B

Def_map = {   # maps anno source to def sources
    Source_719: (Source_719,),
    Source_61B: (Source_719, Source_61B),
    Source_GG: (Source_719,),
}

Anno_map = {  # maps def_source to anno_sources
    Source_719: (Source_719, Source_61B, Source_GG),
    Source_61B: (Source_61B,),
}


@transaction.atomic
def run(*args):
    if 'help' in args:
        print("load_definitions help:")
        print("  This loads references to terms defined in def-docs (719 or 61b) as")
        print("  opp_annotations where these terms are used in anno-docs (719, 61b or gg).")
        print()
        print("  719 definitions are loaded into all documents (719, 61B and GG).")
        print("  61B definitions are only loaded into the 61B document.")
        print()
        print("  python manage.py runscript load_definitions")
        print("    Loads terms defined in all def-docs as opp_annotations where used in all")
        print("    anno-docs.")
        print("  python manage.py runscript load_definitions --script-args defs-doc doc_name")
        print("    Loads terms defined in def-doc as opp_annotations where used in all anno-docs.")
        print("  python manage.py runscript load_definitions --script-args defs-ver version_id")
        print("    Loads terms defined in version of def-doc as opp_annotations where used in")
        print("    same version of anno-doc.")
        print("  python manage.py runscript load_definitions --script-args anno-doc doc_name")
        print("    Loads terms defined in all def-docs as opp_annotations where used in anno-doc.")
        print("  python manage.py runscript load_definitions --script-args anno-ver version_id")
        print("    Loads terms defined in all def-docs as opp_annotations where used in")
        print("    version of anno-doc.")
        print("    Uses anno-ver for def_ver for defs from the same source.")
        print("  python manage.py runscript load_definitions --script-args defs-ver version_id")
        print("                                                            anno-ver version_id.")
        print("    Loads terms defined in version of def-doc as opp_annotations where used in")
        print("    version of anno-doc.")
        #print("  python manage.py runscript load_definitions --script-args test")
        #print("    Runs test on get_sentences function.")
        print("  python manage.py runscript load_definitions --script-args help")
        print("    Prints this help message.")
    elif 'test' in args:
        pass
    else:
        anno_version = None
        if 'defs-doc' in args:
            defs_name = args[args.index('defs-doc') + 1]
            defs_version = models.Version.latest(Source_map[defs_name])
        elif 'defs-ver' in args:
            defs_version = int(args[args.index('defs-ver') + 1])
            anno_version = defs_version
        else:
            defs_version = None

        if 'anno-doc' in args:
            anno_name = args[args.index('anno-doc') + 1]
            anno_version = models.Version.latest(Source_map[anno_name])
        elif 'anno-ver' in args:
            anno_version = int(args[args.index('anno-ver') + 1])

        if defs_version is None:
            if anno_version is None:
                for source in Def_sources:
                    defs_version = models.Version.latest(source)
                    anno_versions = [models.Version.latest(anno_source)
                                     for anno_source in Anno_map[source]]
                    load_definitions(defs_version, anno_versions)
            else:
                anno_source = models.Version.objects.get(id=anno_version).source
                def_versions = [(models.Version.latest(def_source)
                                   if anno_source != def_source
                                   else anno_version)
                                for def_source in Def_map[anno_source]]
                for def_version in def_versions:
                    load_definitions(def_version, [anno_version])
        elif anno_version is not None:
            load_definitions(defs_version, [anno_version])
        else:
            anno_versions = [models.Version.latest(anno_source)
                             for anno_source in Anno_map[Source_map[defs_name]]]
            load_definitions(defs_version, anno_versions)

        print("next: python manage.py runscript show_outline")

