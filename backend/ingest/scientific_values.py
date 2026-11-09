"""比较约数限定与当前规范值，不从旧原始文字恢复或改写数值。"""
from decimal import Decimal, InvalidOperation
import re

APPROXIMATE = re.compile(r'^\s*(?:~|≈|∼|约|about\s+|approximately\s+)\s*'
    r'([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)(.*)$', re.IGNORECASE)


def approximate_number_matches(value, raw, unit=None):
    if value is None or isinstance(value, bool) or not isinstance(raw, str): return False
    match = APPROXIMATE.match(raw)
    if not match: return False
    try:
        if Decimal(match[1]) != Decimal(str(value)): return False
    except (InvalidOperation, ValueError): return False
    suffix = match[2].strip().casefold()
    if not suffix or unit is None: return True
    aliases = {'k': ('k', 'kelvin'), '1': ('1', 'dimensionless'),
               'dimensionless': ('1', 'dimensionless')}.get(str(unit).casefold(), (str(unit).casefold(),))
    return any(suffix == alias or suffix.startswith(alias + ' ') or suffix.startswith(alias + '(') for alias in aliases)
