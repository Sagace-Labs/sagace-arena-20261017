"""Allowlisted scorer runtime; task generators and holdouts excluded."""
import json
import math
import sqlite3
import time
def _expected(family, i, data):
    """Pure Python oracle: no SQL, SQLite, reference query or query-result reuse."""
    if family == 'customer_totals':
        rows=[]
        for customer in data['customers']:
            amounts=[o[3] for o in data['orders'] if o[1]==customer[0] and o[2]=='paid' and (i<4 or o[3]>0)]
            if i<6 or len(amounts)>=2:
                rows.append([customer[0],len(amounts),sum(amounts)])
        return sorted(rows)
    if family == 'missing_completions':
        return sorted([[p[0]] for p in data['people'] if (i<4 or p[1]==1) and not any(c[0]==p[0] and c[1]=='safety' and (i<6 or c[2]==1) for c in data['completions'])])
    if family == 'latest_measurement':
        rows=[]
        for device in data['devices']:
            readings=[x for x in data['readings'] if x[1]==device[0] and (i<4 or x[4]==1)]
            if readings:
                latest=max(readings,key=lambda x:(x[2],x[0]))
                rows.append([device[0],latest[0],latest[3]])
            elif i>=6: rows.append([device[0],None,None])
        return sorted(rows)
    if family == 'running_ledger':
        rows=[]
        for entry in sorted(data['entries'],key=lambda x:(x[1],x[2],x[0])):
            if i>=4 and entry[4]!=1: continue
            previous=[x[3] for x in data['entries'] if x[1]==entry[1] and (x[2],x[0]) <= (entry[2],entry[0]) and (i<4 or x[4]==1)]
            rows.append([entry[0],entry[1],sum(previous)+(100 if i>=6 else 0)])
        return rows
    if family == 'required_skills':
        needed={x[0] for x in data['required']}
        rows=[]
        for p in data['people']:
            possessed={s[1] for s in data['skills'] if s[0]==p[0] and (i<4 or s[2]==1)}
            if needed <= possessed and (i<6 or possessed <= needed): rows.append([p[0]])
        return sorted(rows)
    rows=[]
    for a in data['bookings']:
        for b in data['bookings']:
            if a[0]>=b[0] or a[1]!=b[1]: continue
            if i>=4 and (a[4] or b[4]): continue
            if a[2]<b[3] and b[2]<a[3]:
                duration=min(a[3],b[3])-max(a[2],b[2])
                if i<6 or duration>=2: rows.append([a[0],b[0],duration])
    return sorted(rows)

SAFE_FUNCTIONS={'count','sum','total','min','max','coalesce','ifnull','nullif','abs','round',
                'row_number','rank','dense_rank','lag','lead','first_value','last_value','nth_value',
                'lower','upper','length','substr','substring','trim','ltrim','rtrim'}

def _execute(schema, rows, sql):
    try:
        valid=isinstance(sql,str) and 1<=len(sql.encode('utf-8'))<=16000
    except UnicodeEncodeError:
        valid=False
    if not valid:
        return {'status':'invalid','error':'SQL must be a string of 1 to 16000 UTF-8 bytes'}
    conn=sqlite3.connect(':memory:')
    try:
        for table,definition in schema.items():
            conn.execute(f'CREATE TABLE {table} ({definition})')
            if rows[table]:
                conn.executemany(f'INSERT INTO {table} VALUES ({",".join("?" for _ in rows[table][0])})',rows[table])
        conn.commit()
        for category,value in [('SQLITE_LIMIT_LENGTH',65536),('SQLITE_LIMIT_SQL_LENGTH',16000),
                               ('SQLITE_LIMIT_COLUMN',32),('SQLITE_LIMIT_EXPR_DEPTH',40),
                               ('SQLITE_LIMIT_COMPOUND_SELECT',8),('SQLITE_LIMIT_VARIABLE_NUMBER',0),
                               ('SQLITE_LIMIT_FUNCTION_ARG',16),('SQLITE_LIMIT_ATTACHED',0)]:
            conn.setlimit(getattr(sqlite3,category),value)
        def authorize(action, arg1, arg2, database, source):
            if action==sqlite3.SQLITE_SELECT: return sqlite3.SQLITE_OK
            if action==sqlite3.SQLITE_READ:
                # SQLite emits virtual row-count reads for CTEs/subqueries with
                # no database or column. Their physical source reads are still
                # authorized independently; do not grant unknown physical tables.
                if database is None and arg2=='': return sqlite3.SQLITE_OK
                if database=='main' and arg1 in schema: return sqlite3.SQLITE_OK
            if action==sqlite3.SQLITE_FUNCTION and (arg2 or '').lower() in SAFE_FUNCTIONS: return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        conn.set_authorizer(authorize)
        deadline=time.monotonic()+0.25
        ticks=0
        def progress():
            nonlocal ticks
            ticks+=1
            return int(ticks>200 or time.monotonic()>deadline)
        conn.set_progress_handler(progress,1000)
        cur=conn.execute(sql)
        if cur.description is None:
            return {'status':'invalid','error':'A result-producing SELECT is required'}
        result=cur.fetchmany(501)
        if len(result)>500: return {'status':'limit','error':'Result exceeds 500 rows'}
        result=[list(row) for row in result]
        if any(type(value) not in (int,float,str,type(None)) for row in result for value in row):
            return {'status':'invalid','error':'Binary values are unsupported'}
        if any(type(value) is float and not math.isfinite(value) for row in result for value in row):
            return {'status':'invalid','error':'Nonfinite values are unsupported'}
        columns=[c[0] for c in cur.description]
        if len(json.dumps({'columns':columns,'rows':result},ensure_ascii=True).encode())>65536:
            return {'status':'limit','error':'Result exceeds 65536 bytes'}
        return {'status':'ok','columns':columns,'rows':result}
    except (sqlite3.Error,ValueError,OverflowError) as exc:
        return {'status':'invalid','error':str(exc)[:240]}
    finally:
        conn.close()

def query_public(task, sql):
    return _execute(task['public_data']['schema'],task['public_data']['rows'],sql)

def grade(task, answer):
    if not isinstance(answer,dict) or set(answer)!={'sql'} or not isinstance(answer['sql'],str):
        return {'status':'graded','reward':0,'checks':[{'id':'sql_format','status':'failed'}]}
    family=task['family'].split('/')[-1]
    checks=[]
    datasets=[task['public_data']['rows']]+task['expected']['datasets']
    for index,data in enumerate(datasets):
        result=_execute(task['public_data']['schema'],data,answer['sql'])
        correct=result['status']=='ok' and result['rows']==_expected(family,task['expected']['index'],data)
        checks.append({'id':f'behavior_{index:02}', 'status':'passed' if correct else 'failed'})
    return {'status':'graded','reward':int(all(c['status']=='passed' for c in checks)),'checks':checks}
