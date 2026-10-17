"""Data-only episode engine, independent of the OpenEnv transport."""
import copy
import hashlib
import json
import math
from uuid import uuid4

from arena.catalog import grader_for, load_catalog, public_task

MAX_ACTION_BYTES = 20000
MAX_CALLS = 16
MAX_OBSERVATION_BYTES = 20000


def unique_object(pairs):
    result = {}
    for k,v in pairs:
        if k in result:
            raise ValueError('duplicate JSON key')
        result[k]=v
    return result


def parse_json(text):
    if not isinstance(text,str) or len(text.encode('utf-8')) > MAX_ACTION_BYTES:
        raise ValueError('action size limit')
    def constant(_):
        raise ValueError('nonfinite JSON number')
    value=json.loads(text,object_pairs_hook=unique_object,parse_constant=constant)
    # exponent overflow (1e999) is not covered by parse_constant.
    canonical_json(value)
    return value


def canonical_json(value):
    try:
        return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
    except (ValueError,TypeError,RecursionError,OverflowError) as exc:
        raise ValueError('invalid JSON value') from exc


class Episode:
    def __init__(self, catalog=None, max_calls=MAX_CALLS, calculator_version='v2'):
        if calculator_version=='v2':
            from arena.calculator_v2 import calculate,HELP
        elif calculator_version=='v1':
            from arena.calculator import calculate,HELP
        else:
            raise ValueError('unknown calculator version')
        self.calculate=calculate;self.calculator_help=HELP
        self.catalog=copy.deepcopy(catalog if catalog is not None else load_catalog())
        self.max_calls=max_calls
        self.task=None
        self.done=False
        self.step_count=0
        self.episode_id=None
        self.result=None
        self.submission=None
        self.submission_sha256=None
        self._terminal=None

    def reset(self, task_id=None, episode_id=None):
        task_id=task_id or next(iter(self.catalog))
        if task_id not in self.catalog:
            raise ValueError('unknown selected task_id')
        self.task=copy.deepcopy(self.catalog[task_id])
        self.episode_id=episode_id or str(uuid4())
        self.done=False;self.step_count=0;self.result=None
        self.submission=None;self.submission_sha256=None;self._terminal=None
        t=public_task(self.task)
        initial=self._observation('ready',{'task_id':t['id'],'prompt':t['prompt'],'data':t['public_data'],
            'operations':'read: optional JSON pointer into public data; query: SQL tasks only; calculate: bounded arithmetic; submit: terminal answer object; finish: terminal current answer',
            'calculator':self.calculator_help,
            'action_limit':self.max_calls})
        if initial['output'] is None:
            raise RuntimeError('initial task exceeds observation limit')
        return initial

    def _observation(self,text,output=None,reward=None,done=False):
        obs={'text':text,'output':output,'done':done,'reward':reward}
        if len(canonical_json(obs).encode())>MAX_OBSERVATION_BYTES:
            return {'text':'Output exceeds observation limit. Narrow the request.','output':None,'done':done,'reward':reward}
        return obs

    def finish(self, answer=None):
        if self.done:
            return copy.deepcopy(self._terminal)
        if self.task is None:
            raise RuntimeError('reset required')
        if answer is not None:
            self.submission=copy.deepcopy(answer)
        payload=canonical_json(self.submission)
        self.submission_sha256=hashlib.sha256(payload.encode()).hexdigest()
        try:
            result=grader_for(self.task)(self.task,copy.deepcopy(self.submission))
        except Exception as exc:
            raise RuntimeError('trusted grader failed') from exc
        reward=result.get('reward')
        if result.get('status')!='graded' or type(reward) not in (int,float) or not math.isfinite(reward) or not 0<=reward<=1:
            raise RuntimeError('invalid trusted grading result')
        self.result=copy.deepcopy(result)
        self.done=True
        self._terminal=self._observation('Submission received.',reward=float(reward),done=True)
        return copy.deepcopy(self._terminal)

    def step(self,action):
        if self.done:
            return copy.deepcopy(self._terminal)
        if self.task is None:
            raise RuntimeError('reset required')
        self.step_count+=1
        try:
            if len(canonical_json(action).encode())>MAX_ACTION_BYTES:
                raise ValueError('action size limit')
            if not isinstance(action,dict) or set(action)-{'op','answer','sql','path','expression','notes','metadata'}:
                raise ValueError('unknown action fields')
            op=action.get('op')
            if op not in ('read','query','calculate','submit','finish'):
                raise ValueError('unknown operation')
            if op in ('submit','finish'):
                answer=action.get('answer')
                if answer is not None and not isinstance(answer,dict):
                    raise ValueError('answer must be an object')
                return self.finish(answer)
            if self.step_count>=self.max_calls:
                return self.finish()
            if op=='calculate':
                try:
                    result=self.calculate(action.get('expression'),self.task['public_data'])
                except (ValueError,SyntaxError) as exc:
                    return self._observation('Calculation rejected: '+str(exc)[:180]+'. Use the documented finite expression functions; submit is a separate action.')
                return self._observation('Calculation result.',result)
            if op=='read':
                path=action.get('path') or ''
                if not isinstance(path,str) or len(path)>256:
                    raise ValueError('invalid public JSON pointer')
                value=self.task['public_data']
                if path:
                    if not path.startswith('/'):
                        raise ValueError('path must be a JSON pointer into public data')
                    for token in path[1:].split('/'):
                        token=token.replace('~1','/').replace('~0','~')
                        if isinstance(value,list) and token.isdecimal() and len(token)<8:
                            value=value[int(token)]
                        elif isinstance(value,dict):
                            value=value[token]
                        else:
                            raise ValueError('public path unavailable')
                return self._observation('Public data.',copy.deepcopy(value))
            if not self.task['id'].startswith('sql-'):
                raise ValueError('query is available only for SQL tasks')
            from arena.families.sql_bank import query_public
            output=query_public(self.task,action.get('sql'))
            return self._observation('Query result.',output)
        except (ValueError,KeyError,IndexError,TypeError,RecursionError,SyntaxError):
            if self.step_count>=self.max_calls:
                return self.finish()
            # Fixed public diagnostics cannot echo a private lookup value.
            return self._observation('Invalid action or unavailable public path.')
