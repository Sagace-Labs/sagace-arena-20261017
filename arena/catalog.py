"""Trusted task selection; release catalog contains selected instances only."""
import copy
import json
import os
from pathlib import Path


def build_all_tasks():
    from arena.families import math_bank, science_bank, sql_bank, wine_bank, baci_bank
    tasks = math_bank.build_tasks()+science_bank.build_tasks()+sql_bank.build_tasks()+wine_bank.build_tasks()+baci_bank.build_tasks()
    ids = [t['id'] for t in tasks]
    if len(ids) != len(set(ids)):
        raise RuntimeError('duplicate task IDs')
    return tasks


def load_catalog(path=None):
    selected = Path(path) if path else Path(__file__).with_name('selected_tasks.json')
    if os.environ.get('SAGACE_REQUIRE_SELECTION')=='1' and not selected.is_file():
        raise RuntimeError('release selected catalog missing')
    tasks = json.loads(selected.read_text(encoding='utf-8')) if selected.is_file() else [
        t for t in build_all_tasks() if t['split']=='train']
    if not tasks or len({t['id'] for t in tasks}) != len(tasks):
        raise RuntimeError('invalid selected catalog')
    return {t['id']:t for t in tasks}


def public_task(task):
    return copy.deepcopy({k:task[k] for k in ('id','family','difficulty','prompt','public_data')})


def grader_for(task):
    if task['id'].startswith('math-'):
        from arena.families.math_bank import grade
    elif task['id'].startswith('science-'):
        from arena.families.science_bank import grade
    elif task['id'].startswith('sql-'):
        from arena.families.sql_bank import grade
    else:
        raise RuntimeError('unknown trusted task domain')
    return grade
