# sources.py

from operating_procedures.scripts.scrape_html import (
    fl_leg_domain as Source_719,
    casetext_domain as Source_61B
)

from operating_procedures.scripts.scrape_bylaws import Source as Source_GG


Sources = Source_719, Source_61B, Source_GG


Source_map = {
    '719': Source_719,
    '61b': Source_61B,
    '61B': Source_61B,
    'GG': Source_GG,
    'gg': Source_GG,
}
