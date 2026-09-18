"""Strategy family registry for tournament v1."""
from . import families

def all_variants():
    return families.build_variants()
