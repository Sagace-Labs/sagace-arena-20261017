"""Allowlisted scorer runtime; task generators and holdouts excluded."""
import re
from fractions import Fraction
def grade(task, answer):
    """Bounded grammar, no expression evaluation; infrastructure defects propagate."""
    valid = isinstance(answer, dict) and set(answer) == {'value'}
    value = answer.get('value') if valid else None
    if type(value) is int:
        valid = value.bit_length() <= 512
        value = str(value) if valid else None
    elif isinstance(value, str):
        value = value.strip() if len(value) <= 320 else None
        valid = value is not None and re.fullmatch(r'[+-]?[0-9]{1,150}(?:/[+-]?[0-9]{1,150})?', value) is not None
    else:
        valid = False
    parsed = None
    if valid:
        try:
            parts=value.split('/')
            parsed = Fraction(int(parts[0]),int(parts[1])) if len(parts)==2 else Fraction(int(value))
        except (ValueError, ZeroDivisionError):
            valid = False
    correct = valid and parsed == Fraction(task['expected'])
    return {'status': 'graded', 'reward': int(correct), 'checks': [
        {'id': 'answer_format', 'status': 'passed' if valid else 'failed'},
        {'id': 'exact_value', 'status': ('passed' if correct else 'failed') if valid else 'skipped'}]}
