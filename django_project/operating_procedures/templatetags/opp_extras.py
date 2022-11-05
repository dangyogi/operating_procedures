# opp_extras.py

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe


register = template.Library()

@register.filter(needs_autoescape=True)
@stringfilter
def savespaces(text, autoescape=True):
    if not text or text[0] != ' ' and text[-1] != ' ':
        return text
    text_start = ''
    text_end = ''
    if text[0] == ' ':
        text_start = '&#32;'
        text = text[1:]
    if text and text[-1] == ' ':
        text_end = '&#32;'
        text = text[:-1]
    if autoescape:
        text = conditional_escape(text)
    return mark_safe(text_start + text + text_end)
