"""Bounded arithmetic interpreter over public JSON; never Python eval/exec."""
import ast
import math
import operator


HELP = ('calculate uses expression with data=public data; arithmetic + - * / ** %, list literals, '
        'JSON subscripts, and functions sum,min,max,len,mean,var,sqrt,log,exp,abs, '
        'dot(a,b), col(rows,key), where(rows,key,value), clean(values). '
        'var is sample variance (n-1); clean drops nulls; other numeric functions reject nulls. '
        'sqrt/log/exp/abs accept a number or array. Limits: 4096 expression chars, 256 AST nodes, '
        'depth 24, arrays <=512, numeric magnitude <=1e100, |exponent|<=100.')


def calculate(expression, data):
    if not isinstance(expression,str) or not 1<=len(expression)<=4096:
        raise ValueError('expression length')
    tree=ast.parse(expression,mode='eval')
    if sum(1 for _ in ast.walk(tree))>256:
        raise ValueError('expression node limit')
    work=0
    def number(v):
        if type(v) not in (int,float) or abs(v)>1e100 or not math.isfinite(v):
            raise ValueError('finite bounded number required')
        return v
    def vector(v):
        if not isinstance(v,list) or len(v)>512:
            raise ValueError('bounded array required')
        return [number(x) for x in v]
    def checked(v,depth=0):
        nonlocal work
        work+=1
        if work>20000 or depth>24:
            raise ValueError('calculation work/depth limit')
        if type(v) in (int,float): return number(v)
        if isinstance(v,list):
            if len(v)>512: raise ValueError('array limit')
            return [checked(x,depth+1) for x in v]
        if isinstance(v,dict):
            if len(v)>512: raise ValueError('mapping limit')
            return {k:checked(x,depth+1) for k,x in v.items()}
        if v is None or isinstance(v,str): return v
        raise ValueError('unsupported value')
    def call(name,args):
        if name=='col' and len(args)==2:
            rows,key=args
            if not isinstance(rows,list) or len(rows)>512 or type(key) not in (str,int):
                raise ValueError('col arguments')
            return [row[key] for row in rows]
        if name=='where' and len(args)==3:
            rows,key,value=args
            if not isinstance(rows,list) or len(rows)>512 or type(key) not in (str,int):
                raise ValueError('where arguments')
            return [row for row in rows if row[key]==value]
        if name=='clean' and len(args)==1 and isinstance(args[0],list):
            return [v for v in args[0] if v is not None]
        if name=='len' and len(args)==1 and isinstance(args[0],(list,dict,str)):
            return len(args[0])
        if name=='dot' and len(args)==2:
            a,b=map(vector,args)
            if len(a)!=len(b): raise ValueError('dot length mismatch')
            return math.fsum(number(x*y) for x,y in zip(a,b))
        if name in ('sqrt','log','exp','abs') and len(args)==1:
            f={'sqrt':math.sqrt,'log':math.log,'exp':math.exp,'abs':abs}[name]
            return [number(f(x)) for x in vector(args[0])] if isinstance(args[0],list) else number(f(number(args[0])))
        if name in ('sum','min','max','mean','var') and len(args)==1:
            values=vector(args[0])
            if name=='sum': return math.fsum(values)
            if not values: raise ValueError('empty numeric array')
            if name=='min': return min(values)
            if name=='max': return max(values)
            mean=math.fsum(values)/len(values)
            if name=='mean': return mean
            if len(values)<2: raise ValueError('sample variance needs two values')
            return math.fsum((x-mean)**2 for x in values)/(len(values)-1)
        raise ValueError('unsupported function or arguments')
    def visit(node,depth=0):
        nonlocal work
        work+=1
        if work>20000 or depth>24: raise ValueError('work/depth limit')
        child=lambda n:visit(n,depth+1)
        if isinstance(node,ast.Constant): return checked(node.value)
        if isinstance(node,ast.Name) and node.id=='data': return data
        if isinstance(node,ast.List): return checked([child(x) for x in node.elts])
        if isinstance(node,ast.Subscript):
            obj,key=child(node.value),child(node.slice)
            if isinstance(obj,(list,dict)) and type(key) in (str,int): return obj[key]
            raise ValueError('subscript requires public list/dictionary')
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            x=number(child(node.operand));return x if isinstance(node.op,ast.UAdd) else -x
        if isinstance(node,ast.BinOp) and type(node.op) in (ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow,ast.Mod):
            a,b=number(child(node.left)),number(child(node.right))
            if isinstance(node.op,ast.Pow) and abs(b)>100: raise ValueError('exponent limit')
            result={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,
                    ast.Pow:operator.pow,ast.Mod:operator.mod}[type(node.op)](a,b)
            return number(result)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and not node.keywords:
            return checked(call(node.func.id,[child(x) for x in node.args]))
        raise ValueError('unsupported expression syntax')
    try:
        result=checked(visit(tree.body))
        # A calculator produces numbers/arrays, not an additional arbitrary JSON read.
        return vector(result) if isinstance(result,list) else number(result)
    except (ArithmeticError,KeyError,IndexError,TypeError,RecursionError) as exc:
        raise ValueError('invalid calculation') from exc
