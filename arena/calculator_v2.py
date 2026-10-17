"""Finite arithmetic DSL with interpreted comprehensions; no host eval/exec.

Staged revision: import explicitly for qualification before changing a live pilot.
"""
import ast
import itertools
import math
import operator

HELP=('calculate accepts a bounded Python-like expression, not a script. data is the public JSON. '
      'Use arithmetic, comparisons, and finite list/generator comprehensions with sum/all/any; '
      'range, product, combinations, enumerate, zip, len, comb, factorial, abs, sqrt,log,exp, '
      'min,max,mean,var,dot,col,where,clean are available. Examples: '
      'sum(1 for x in product(range(3),range(4)) if x[0]+x[1]==3); '
      'mean(clean(col(where(data["rows"],0,"male"),1))). '
      'No assignments, imports, attributes, lambdas, loops as statements, recursion or files. '
      'Limits:4096 chars,512 AST nodes,depth32,<=65536 items per finite iterator, '
      '<=1000000 cumulative interpreter/work steps,output arrays<=512,|number|<=1e100,|power|<=100. '
      'Use submit with an answer object for the final result; calculation results are not submissions.')


class Finite:
    """A lazy finite iterator with a proven upper bound, reusable as a value."""
    def __init__(self,factory,size,exact=True):
        if type(size) is not int or not 0<=size<=65536:
            raise ValueError('finite iterator cardinality limit')
        self.factory=factory;self.size=size;self.exact=exact

    def __iter__(self):return self.factory()


def calculate(expression,data,work_limit=1000000):
    if not isinstance(expression,str) or not 1<=len(expression)<=4096:
        raise ValueError('expression length limit')
    tree=ast.parse(expression,mode='eval')
    if sum(1 for _ in ast.walk(tree))>512:
        raise ValueError('expression node limit')
    work=0
    def tick(amount=1):
        nonlocal work
        work+=amount
        if work>work_limit:raise ValueError('cumulative calculation work limit')
    def numeric(v,booleans=False):
        if booleans and type(v) is bool:return int(v)
        if type(v) not in (int,float) or abs(v)>1e100 or not math.isfinite(v):
            raise ValueError('bounded finite number required')
        return v
    def integer(v):
        if type(v) is not int or abs(v)>1000000:raise ValueError('bounded integer required')
        return v
    def bounded_iter(v):
        if isinstance(v,Finite):return v
        if isinstance(v,(list,tuple,range)) and len(v)<=65536:
            return Finite(lambda:iter(v),len(v))
        raise ValueError('finite iterable required')
    def items(v):
        for i,x in enumerate(bounded_iter(v)):
            tick()
            if i>=65536:raise ValueError('iterator cardinality limit')
            yield x
    def checked(v,depth=0):
        tick()
        if depth>32:raise ValueError('value depth limit')
        if type(v) in (int,float):return numeric(v)
        if type(v) is bool or v is None or isinstance(v,str):return v
        if isinstance(v,Finite):return v
        if isinstance(v,(list,tuple)):
            if len(v)>512:raise ValueError('array limit')
            return [checked(x,depth+1) for x in v]
        if isinstance(v,dict):
            if len(v)>512:raise ValueError('mapping limit')
            return {k:checked(x,depth+1) for k,x in v.items()}
        raise ValueError('unsupported result value')
    def assign(target,value,env):
        tick()
        if isinstance(target,ast.Name) and target.id not in ('data',):
            env[target.id]=value;return
        if isinstance(target,(ast.Tuple,ast.List)) and isinstance(value,(list,tuple)) and len(target.elts)==len(value):
            for t,x in zip(target.elts,value):assign(t,x,env)
            return
        raise ValueError('comprehension target must be a local name or unpacking tuple')
    def call(name,args,kwargs):
        tick()
        if kwargs and (name!='product' or set(kwargs)!={'repeat'}):raise ValueError('unsupported keyword')
        if name=='range' and 1<=len(args)<=3 and not kwargs:
            values=[integer(x) for x in args]
            r=range(*values);return bounded_iter(r)
        if name=='product':
            repeat=integer(kwargs.get('repeat',1))
            if not 0<=repeat<=16:raise ValueError('product repeat limit')
            sources=[bounded_iter(v) for v in args]*repeat
            size=math.prod(v.size for v in sources)
            if size>65536:raise ValueError('product cardinality limit')
            # itertools.product caches finite pools. Debit all materialized values.
            pools=[tuple(items(v)) for v in sources]
            return Finite(lambda:itertools.product(*pools),math.prod(len(v) for v in pools))
        if name=='combinations' and len(args)==2:
            source=bounded_iter(args[0]);r=integer(args[1])
            if not 0<=r<=source.size:raise ValueError('combination size')
            size=math.comb(source.size,r)
            if size>65536:raise ValueError('combination cardinality limit')
            pool=tuple(items(source))
            return Finite(lambda:itertools.combinations(pool,r),math.comb(len(pool),r) if r<=len(pool) else 0)
        if name=='enumerate' and len(args)==1:
            source=bounded_iter(args[0]);return Finite(lambda:enumerate(items(source)),source.size,source.exact)
        if name=='zip' and args:
            sources=[bounded_iter(a) for a in args]
            return Finite(lambda:zip(*(items(v) for v in sources)),min(v.size for v in sources),all(v.exact for v in sources))
        if name=='len' and len(args)==1:
            if isinstance(args[0],Finite):
                if not args[0].exact:raise ValueError('len(generator) unavailable; use sum(1 for x in ...)')
                return args[0].size
            if isinstance(args[0],(list,tuple,dict,str)):return len(args[0])
        if name in ('comb','factorial'):
            ns=[integer(a) for a in args]
            if name=='comb' and len(ns)==2 and 0<=ns[1]<=ns[0]<=512:return numeric(math.comb(*ns))
            if name=='factorial' and len(ns)==1 and 0<=ns[0]<=69:return math.factorial(ns[0])
            raise ValueError('comb/factorial argument limit')
        if name in ('sum','all','any','min','max','mean','var') and len(args)==1:
            values=items(args[0])
            if name=='all':return all(values)
            if name=='any':return any(values)
            if name=='sum':
                total=0
                for value in values:total=numeric(total+numeric(value,True))
                return total
            if name in ('min','max'):
                return numeric((min if name=='min' else max)(numeric(v) for v in values))
            # Statistical arrays stay small; no unbounded list is accumulated.
            array=[]
            for value in values:
                if len(array)>=512:raise ValueError('statistical array limit')
                array.append(numeric(value))
            if not array:raise ValueError('empty statistical array')
            mean=math.fsum(array)/len(array)
            if name=='mean':return mean
            if len(array)<2:raise ValueError('sample variance needs two observations')
            return numeric(math.fsum((v-mean)**2 for v in array)/(len(array)-1))
        if name in ('sqrt','log','exp','abs') and len(args)==1:
            f={'sqrt':math.sqrt,'log':math.log,'exp':math.exp,'abs':abs}[name]
            if isinstance(args[0],(list,tuple)):
                tick(len(args[0]));return [numeric(f(numeric(x))) for x in args[0]]
            return numeric(f(numeric(args[0])))
        if name=='dot' and len(args)==2:
            a,b=map(bounded_iter,args)
            if a.size!=b.size or a.size>512:raise ValueError('dot array length')
            return numeric(math.fsum(numeric(x)*numeric(y) for x,y in zip(items(a),items(b))))
        if name in ('col','where','clean'):
            # Generic JSON table operations, independent of task answers.
            if name=='clean' and len(args)==1:
                return checked([v for v in items(args[0]) if v is not None])
            if name=='col' and len(args)==2:
                return checked([row[args[1]] for row in items(args[0])])
            if name=='where' and len(args)==3:
                return checked([row for row in items(args[0]) if row[args[1]]==args[2]])
        raise ValueError('unsupported function or arguments')
    def visit(node,env,depth=0):
        tick()
        if depth>32:raise ValueError('expression depth limit')
        child=lambda n:visit(n,env,depth+1)
        if isinstance(node,ast.Constant):return checked(node.value)
        if isinstance(node,ast.Name) and node.id in env:return env[node.id]
        if isinstance(node,(ast.List,ast.Tuple)):return checked([child(x) for x in node.elts])
        if isinstance(node,ast.Subscript):
            obj,key=child(node.value),child(node.slice)
            if isinstance(obj,(list,tuple,dict,str)) and type(key) in (str,int):return obj[key]
            raise ValueError('subscript requires public array/dictionary')
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub,ast.Not)):
            value=child(node.operand)
            if isinstance(node.op,ast.Not):return not value
            value=numeric(value);return value if isinstance(node.op,ast.UAdd) else -value
        if isinstance(node,ast.BoolOp):
            if isinstance(node.op,ast.And):
                for n in node.values:
                    if not child(n):return False
                return True
            if isinstance(node.op,ast.Or):
                for n in node.values:
                    if child(n):return True
                return False
        if isinstance(node,ast.Compare):
            a=child(node.left)
            operations={ast.Eq:operator.eq,ast.NotEq:operator.ne,ast.Lt:operator.lt,ast.LtE:operator.le,
                        ast.Gt:operator.gt,ast.GtE:operator.ge}
            for op,n in zip(node.ops,node.comparators):
                b=child(n)
                if isinstance(op,(ast.Is,ast.IsNot)):
                    if not (a is None or b is None or type(a) is bool or type(b) is bool):
                        raise ValueError('identity comparison is only available for null/booleans')
                    result=(a is b) if isinstance(op,ast.Is) else (a is not b)
                elif isinstance(op,(ast.In,ast.NotIn)):
                    result=any(a==x for x in items(b))
                    if isinstance(op,ast.NotIn):result=not result
                elif type(op) in operations:
                    result=operations[type(op)](a,b)
                else:raise ValueError('unsupported comparison')
                if not result:return False
                a=b
            return True
        if isinstance(node,ast.IfExp):return child(node.body) if child(node.test) else child(node.orelse)
        if isinstance(node,ast.BinOp):
            a,b=numeric(child(node.left)),numeric(child(node.right))
            ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,
                 ast.FloorDiv:operator.floordiv,ast.Pow:operator.pow,ast.Mod:operator.mod,
                 ast.BitAnd:operator.and_,ast.BitOr:operator.or_,ast.BitXor:operator.xor,ast.RShift:operator.rshift,ast.LShift:operator.lshift}
            if type(node.op) not in ops:raise ValueError('unsupported arithmetic')
            if isinstance(node.op,ast.Pow) and abs(b)>100:raise ValueError('power limit')
            if isinstance(node.op,(ast.LShift,ast.RShift)) and (type(b) is not int or not 0<=b<=100):raise ValueError('shift limit')
            return numeric(ops[type(node.op)](a,b))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
            if any(k.arg is None for k in node.keywords):raise ValueError('no keyword expansion')
            return checked(call(node.func.id,[child(x) for x in node.args],{k.arg:child(k.value) for k in node.keywords}))
        if isinstance(node,(ast.GeneratorExp,ast.ListComp)):
            if len(node.generators)>16:raise ValueError('comprehension nesting limit')
            if any(g.is_async for g in node.generators):raise ValueError('async iteration unavailable')
            # Bound cardinality dynamically through the global work counter;
            # inner iterable sizes cannot multiply past the cumulative work cap.
            def generate(level,scope):
                if level==len(node.generators):yield visit(node.elt,scope,depth+1);return
                g=node.generators[level]
                iterable=visit(g.iter,scope,depth+1)
                for value in items(iterable):
                    local=dict(scope);assign(g.target,value,local)
                    if all(visit(test,local,depth+1) for test in g.ifs):yield from generate(level+1,local)
            # A generator's declared upper bound is conservative; consuming it
            # still spends cumulative ticks, including every filtered-out item.
            result=Finite(lambda:generate(0,dict(env)),65536,False)
            if isinstance(node,ast.ListComp):
                output=[]
                for value in items(result):
                    if len(output)>=512:raise ValueError('comprehension output array limit')
                    output.append(value)
                return checked(output)
            return result
        raise ValueError('unsupported syntax; use bounded expressions, not Python scripts')
    try:
        result=checked(visit(tree.body,{'data':data}))
        if type(result) is bool:return result
        if isinstance(result,list):
            return [numeric(v,True) for v in result]
        return numeric(result)
    except (ArithmeticError,KeyError,IndexError,TypeError,RecursionError) as exc:
        raise ValueError('invalid finite calculation') from exc
