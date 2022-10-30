from django.db import models

# Create your models here.


class Version(models.Model):
    upload_date = models.DateField(auto_now_add=True)
    source = models.CharField(max_length=30)
    url = models.CharField(max_length=300, null=True, blank=True)
    wordrefs_loaded = models.BooleanField(default=False)
    definitions_loaded = models.BooleanField(default=False)

    @classmethod
    def latest(cls, source):
        return cls.objects.filter(source=source).order_by('-upload_date')[0].id

class Item(models.Model):
    version = models.ForeignKey(Version, on_delete=models.CASCADE)
    citation = models.CharField(max_length=20)
    number = models.CharField(max_length=20)
    parent = models.ForeignKey('Item', on_delete=models.CASCADE, null=True, blank=True)
    item_order = models.PositiveSmallIntegerField()
    body_order = models.PositiveSmallIntegerField(null=True, blank=True)
    # title is in Paragraph that points back to this Item with body_order == 0
    has_title = models.BooleanField(default=False)
    history = models.CharField(max_length=200, null=True, blank=True)

    def get_title(self):
        r'''Returns the Paragraph object.
        '''
        return self.paragraph_set.get(body_order=0)

    def get_note(self, number):
        r'''Returns the text of the note.
        '''
        i = self
        while True:
            try:
                return Note.objects.get(item=i, number=number)
            except self.DoesNotExist:
                if i.parent is None:
                    raise self.DoesNotExist(f"note {self.citation}")
                i = i.parent

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['version', 'citation'], name='unique_item'),
        ]

class Note(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    number = models.PositiveSmallIntegerField()
    text = models.CharField(max_length=200)

    class Meta:
        ordering = ['number']
        constraints = [
            models.UniqueConstraint(fields=['item', 'number'], name='unique_note'),
        ]

class Paragraph(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, null=True, blank=True)
    cell = models.ForeignKey('TableCell', on_delete=models.CASCADE, null=True, blank=True)
    body_order = models.PositiveSmallIntegerField()  # 0 for Item title
    text = models.CharField(max_length=4000)

    def with_annotations(self):
        r'''Returns spans.

        A span is [type, info, spans] or ['text', None, text].
        '''

        text = self.text
        start = 0
        end = len(text)
        annotations = self.annotation_set.all()

    class Meta:
        ordering = ['body_order']
        constraints = [
            models.UniqueConstraint(fields=['item', 'body_order'], name='unique_paragraph'),
        ]


class chunk:
    def __init__(self, tag, **attrs):
        self.tag = tag
        for name, value in attrs.items():
            setattr(self, name, value)

def chunkify_text(text, annotations, start=0, end=None):
    r'''Returns a list of chunks.
    '''
    if end is None:
        end = len(text)
    ans = []

    def make_annotation(annotations):
        #nonlocal annotations
        nested_annotations = []
        this_annotation = annotations[0]

        # local start, end
        start = this_annotation.char_offset
        end = start + this_annotation.length

        for i, annotation in enumerate(annotations):
            if annotation.char_offset < end:
                if annotation.char_offset + annotation.length <= end:
                    nested_annotations.append(annotation)
                    continue
                # This annotation overlaps the first annotation.  We cut the first
                # annotation short in this case...
                end = annotation.char_offset
                for j in range(len(nested_annotations) - 1, -1, -1):
                    if nested_annotations[j].char_offset >= end:
                        del nested_annotations[j]
                    else:
                        break
            break
        ans.append(make_chunk(this_annotation,
                              chunkify_text(text, nested_annotations, start, end)))
        del annotations[0: len(nested_annotations) + 1]
        return end  # this will be the new start in text

    while start < len(text):
        if not annotations:
            ans.append(chunk('text', text=text[start: end]))
            break
        assert annotations[0].char_offset >= start
        if annotations[0].char_offset > start:
            ans.append(chunk('text', text=text[start: annotations[0].char_offset]))
        start = make_annotation(annotations)  # includes nested annotations
    assert not annotations
    return ans

def make_chunk(annotation, body):
    if annotation.tag == 's_link':
        return chunk('s_link', citation=annotation.info, body=body)
    if annotation.tag == 'note':
        pass
    elif annotation.tag == 'definition':
        pass
    else:
        raise AssertionError(f"Unknown annotation type {annotation.type!r}")

class Annotation(models.Model):
    paragraph = models.ForeignKey(Paragraph, on_delete=models.CASCADE)

    # 's_link' -- an ss. or s. link.  Info is the cite, which could either be a single site
    #             (e.g., '719.106(1)') or a range of cites (e.g., '719.106-719.108').
    # 'note' -- a footnote in the text.  The footnote number is in info, the footnote
    #           itself is in the Note table.
    # 'definition' -- The citation of the definition is in info.
    type = models.CharField(max_length=20)
    char_offset = models.PositiveSmallIntegerField()
    length = models.PositiveSmallIntegerField()
    info = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        ordering = ['char_offset']

class Table(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    body_order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ['body_order']
        constraints = [
            models.UniqueConstraint(fields=['item', 'body_order'], name='unique_table'),
        ]

class TableCell(models.Model):
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    head = models.BooleanField(default=False)
    row = models.PositiveSmallIntegerField()
    col = models.PositiveSmallIntegerField()
  # text is in Paragraph that points back to this TableCell

    class Meta:
        ordering = ['row', 'col']
        constraints = [
            models.UniqueConstraint(fields=['table', 'row', 'col'],
                                    name='unique_table_cell'),
        ]

class Word(models.Model):
    text = models.CharField(max_length=50, unique=True)  # always all lowercase

    @classmethod
    def get_text(cls, id):
        return cls.objects.get(id=id).text

    @classmethod
    def lookup_word(cls, text):
        r'''Gets Word object, creating a new Word if necessary.

        Returns the Word found (or created).

        Converts text to lowercase.
        '''
        text = text.lower()
        try:
            w = Word.objects.get(text=text)
        except cls.DoesNotExist:
            w = Word(text=text)
            w.save()
        return w

    def get_synonyms(self, seen=None):
        if seen is None:
            seen = set((self.id,))
        for s in Synonym.objects.filter(word=self).all():
            if s.synonym_id not in seen:
                seen.add(s.synonym_id)
                s.synonym.get_synonyms(seen)
        return seen

class Synonym(models.Model):
    word = models.ForeignKey(Word, on_delete=models.CASCADE)
    synonym = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='+')

class WordRef(models.Model):
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

