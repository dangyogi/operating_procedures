from django.db import models

# Create your models here.

from itertools import chain, product
from operator import attrgetter

from operating_procedures.chunks import (
    chunkify_text, chunk_item, chunkify_item_body, chunk_paragraph, chunk_table
)


class Version(models.Model):
    upload_date = models.DateField(auto_now_add=True)
    source = models.CharField(max_length=30)
    url = models.CharField(max_length=300, null=True, blank=True)
    wordrefs_loaded = models.BooleanField(default=False)
    definitions_loaded = models.BooleanField(default=False)

    @classmethod
    def latest(cls, source):
        r'''Returns id of latest version of source.
        '''
        return cls.objects.filter(source=source).order_by('-upload_date', '-id')[0].id

    def as_str(self):
        return f"<Version({self.id}) {self.upload_date=}>"

    def __repr__(self):
        return self.as_str()


class Item(models.Model):
    version = models.ForeignKey(Version, on_delete=models.CASCADE)
    citation = models.CharField(max_length=20)
    number = models.CharField(max_length=20)
    parent = models.ForeignKey('Item', on_delete=models.CASCADE, null=True, blank=True)
    item_order = models.PositiveSmallIntegerField()
    body_order = models.PositiveSmallIntegerField(null=True, blank=True)
    num_elements = models.PositiveSmallIntegerField() # not including title
    # title is in Paragraph that points back to this Item with body_order == 0
    has_title = models.BooleanField(default=False)
    #authority = models.CharField(max_length=200, null=True, blank=True)
    #law_implemented = models.CharField(max_length=200, null=True, blank=True)
    #history = models.CharField(max_length=200, null=True, blank=True)

    def as_str(self):
        return f"<Item({self.id}) {self.citation}>"

    def __repr__(self):
        return self.as_str()

    def get_title(self):
        r'''Returns the Paragraph object.
        '''
        if self.has_title:
            return self.paragraph_set.get(body_order=0)
        return None

    def get_body(self):
        r'''Return an iterator over all body objects.

        Important!  Caller must sort by body_order.
        '''
        return chain(self.paragraph_set.exclude(body_order=0).all(),
                     self.table_set.all(),
                     self.item_set.all())

    def get_note(self, number):
        r'''Returns the text of the note.
        '''
        i = self
        while True:
            print(f"{i.citation} looking for {number=!r}")
            try:
                anno = Annotation.objects.get(paragraph__item=i, type='note',
                                              info=str(number))
                return anno.paragraph.text
            except Annotation.DoesNotExist:
                if i.parent is None:
                    raise Annotation.DoesNotExist(f"note {number=} in {self.citation}")
                i = i.parent

    def get_block(self, with_body=True, def_as_link=False):
        return chunk_item(self, with_body, def_as_link)

    def get_body_blocks(self):
        #print(f"{self}.get_body_blocks()")
        return chunkify_item_body(self)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['version', 'citation'],
                                    name='unique_item'),
        ]

''' FIX: Delete
class Note(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    note_order = models.PositiveSmallIntegerField()
    type = models.CharField(max_length=50) # 'History', 'Note', 'Law Implemented', etc
    note_number = models.PositiveSmallIntegerField(null=True, blank=True)
    text = models.CharField(max_length=200)

    def as_str(self):
        if self.note_number is None:
            return f"<Note({self.id}) {self.type} {self.item.as_str()!r}>"
        return f"<Note({self.id}) {self.type} {self.number} {self.item.as_str()!r}>"

    def __repr__(self):
        return self.as_str()

    class Meta:
        ordering = ['note_order']
        constraints = [
            models.UniqueConstraint(fields=['item', 'note_order'],
                                    name='unique_note'),
        ]
'''

class Paragraph(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, null=True, blank=True)
    cell = models.ForeignKey('TableCell', on_delete=models.CASCADE, null=True, blank=True)
    body_order = models.PositiveSmallIntegerField()  # 0 for Item title
    text = models.CharField(max_length=4000)

    def as_str(self):
        return f"<Paragraph({self.id}) {self.item.as_str()} {self.text[:25]!r}>"

    def __repr__(self):
        return self.as_str()

    def parent_item(self):
        r'''Returns the item directly containing this paragraph.
        '''
        if self.item is not None:
            return self.item
        return self.cell.table.item

    def get_block(self, wordrefs=(), def_as_link=False):
        return chunk_paragraph(self, wordrefs=wordrefs, def_as_link=def_as_link)

    def with_annotations(self, wordrefs=(), def_as_link=False):
        annotations = list(self.annotation_set.all())
        if wordrefs:
            #print(f"with_annotations got {wordrefs=}")
            annotations.extend(wordrefs)
            annotations.sort(key=attrgetter('char_offset'))
        #print(f"{self.as_str()}.with_annotations got {annotations}")
        return chunkify_text(self.parent_item(), self.text, annotations,
                             def_as_link=def_as_link)

    class Meta:
        ordering = ['body_order']
        constraints = [
            models.UniqueConstraint(fields=['item', 'body_order'],
                                    name='unique_paragraph'),
        ]

class Annotation(models.Model):
    paragraph = models.ForeignKey(Paragraph, on_delete=models.CASCADE)

    # Local Annotations that only apply to a short piece of text:
    #
    # 's_cite' -- an ss. or s. link.  Info is the cite, which could either be a
    #             single site (e.g., '719.106(1)') or a range of cites
    #             (e.g., '719.106-719.108').  The cite does not include any spaces.
    # 'note_ref' -- a footnote reference in the text.  The footnote number is in
    #               info, the footnote itself is in the related Paragraph with a
    #               'note' Annotation with the same footnote number.
    # 'definition' -- The citation of the definition is in info.
    # 'link' -- an <a> tag in the sources.  Info is the href.
    #
    # Wordrefs appear to be 'search_highlight' annotations with
    # info = word_group_index, but these annotations are not stored in the database.
    #
    # Annotations that identify special kinds of paragraphs:
    #
    # 'citeAs' -- 61B, includes the whole Paragraph.
    #
    # The rest of these only include the title word(s):
    #
    # 'note' -- footnote body for 719.  Info is footnote number.  No other Annotations.
    # 'law_implemented' -- for 61B, separate 's_cite' Annotations for each cite
    # 'specific_authority' -- for 61B, separate 's_cite' Annotations for each cite
    # 'rulemaking_authority' -- for 61B, separate 's_cite' Annotations for each cite
    # 'history' -- 719 and 61B, no other Annotations
    #
    type = models.CharField(max_length=20)
    char_offset = models.PositiveSmallIntegerField()
    length = models.PositiveSmallIntegerField()
    info = models.CharField(max_length=20, null=True, blank=True)

    def as_str(self):
        return f"<Annotation({self.id}) {self.type} " \
               f"paragraph={self.paragraph.as_str()} info={self.info!r}>"

    def __repr__(self):
        return self.as_str()

    class Meta:
        ordering = ['char_offset']

class Table(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    has_header = models.BooleanField(default=False)
    body_order = models.PositiveSmallIntegerField()

    def as_str(self):
        return f"<Table({self.id}) {self.item.as_str()}>"

    def __repr__(self):
        return self.as_str()

    def get_block(self, def_as_link=False):
        return chunk_table(self, def_as_link)

    class Meta:
        ordering = ['body_order']
        constraints = [
            models.UniqueConstraint(fields=['item', 'body_order'], name='unique_table'),
        ]

class TableCell(models.Model):
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    row = models.PositiveSmallIntegerField()
    col = models.PositiveSmallIntegerField()
  # text is in Paragraph that points back to this TableCell

    def get_blocks(self, def_as_link=False):
        return list(map(methodcaller('get_block', def_as_link=def_as_link),
                        self.paragraph_set.all()))

    class Meta:
        ordering = ['row', 'col']
        constraints = [
            models.UniqueConstraint(fields=['table', 'row', 'col'],
                                    name='unique_table_cell'),
        ]

class Word(models.Model):
    text = models.CharField(max_length=50, unique=True)  # always all lowercase

    def as_str(self):
        return f"<Word({self.id}) {self.text}>"

    def __repr__(self):
        return self.as_str()

    @classmethod
    def get_text(cls, id):
        return cls.objects.get(id=id).text

    @classmethod
    def lookup_word(cls, text):
        r'''Gets Word object, creating a new Word if necessary.

        Returns the Word found (or created).

        Converts text to lowercase.
        '''
        return cls.objects.get_or_create(text=text.lower())[0]

    def get_synonyms(self):
        r'''Returns a set of Word.ids (including self.id).
        '''
        return Synonym.get_synonyms(self.id)

class Synonym(models.Model):
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    synonym = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='+')

    @classmethod
    def get_synonyms(cls, word_id):
        ans = set(map(attrgetter('synonym_id'),
                      cls.objects.filter(word_id=word_id).all()))
        ans.add(word_id)
        return ans

    @classmethod
    def add_synonym(cls, word_id, synonym_id):
        if cls.objects.filter(word_id=word_id, synonym_id=synonym_id).exists():
            raise AssertionError(
                    f"add_synonym: duplicate {Word.objects.get(id=word_id).text} "
                    f"{Word.objects.get(id=synonym_id).text}")
        cls.objects.bulk_create(
            chain.from_iterable(
              (cls(word_id=w, synonym_id=s),
               cls(word_id=s, synonym_id=w))
              for w, s in product(cls.get_synonyms(word_id),
                                  cls.get_synonyms(synonym_id))))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['word', 'synonym'],
                                    name='unique_synonym'),
        ]

class WordRef(models.Model):
    type = 'search_highlight'  # word_group_index inserted as 'info' to make this
                               # look like an annotation with type 'search_highlight'.
    paragraph = models.ForeignKey(Paragraph, on_delete=models.CASCADE)
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    sentence_number = models.PositiveSmallIntegerField()
    word_number = models.PositiveSmallIntegerField()
    char_offset = models.PositiveSmallIntegerField()
    length = models.PositiveSmallIntegerField()

    def get_next_word(self):
        #print(f"get_next_word at {self.paragraph_id=} {self.sentence_number=} "
        #      f"{self.word_number}")
        return WordRef.objects.get(paragraph_id=self.paragraph_id,
                                   sentence_number=self.sentence_number,
                                   word_number=self.word_number + 1)

    class Meta:
        ordering = ['sentence_number', 'word_number']
        constraints = [
            models.UniqueConstraint(fields=['paragraph', 'word', 'sentence_number',
                                            'word_number'],
                                    name='unique_wordref'),
        ]

