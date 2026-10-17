"""Real pinned OpenEnv bridge. Import requires the declared SDK dependency."""
from typing import Any, Literal
from pydantic import Field, model_validator
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import Action, Observation, State
from openenv.core.env_server.http_server import create_app
from starlette.responses import JSONResponse

from arena.environment import Episode, MAX_ACTION_BYTES, canonical_json, parse_json


class ArenaAction(Action):
    op: Literal['read','query','calculate','submit','finish']
    answer: dict[str,Any] | None = None
    sql: str | None = Field(default=None,max_length=16000)
    path: str | None = Field(default=None,max_length=256)
    expression: str | None = Field(default=None,max_length=4096)
    notes: str | None = Field(default=None,max_length=4096,description='Optional brief calculation or decision notes; not scored.')

    @model_validator(mode='after')
    def bounded(self):
        if len(canonical_json(self.model_dump()).encode())>MAX_ACTION_BYTES:
            raise ValueError('action exceeds byte limit')
        return self


class ArenaObservation(Observation):
    text: str
    output: Any = None


class ArenaEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS=True

    def __init__(self):
        super().__init__()
        self.episode=Episode()

    def reset(self,seed=None,episode_id=None,task_id=None,**kwargs):
        return ArenaObservation(**self.episode.reset(task_id=task_id,episode_id=episode_id))

    def step(self,action,timeout_s=None,**kwargs):
        return ArenaObservation(**self.episode.step(action.model_dump()))

    @property
    def state(self):
        return State(episode_id=self.episode.episode_id,step_count=self.episode.step_count)


app=create_app(ArenaEnvironment,ArenaAction,ArenaObservation,env_name='sagace_arena',max_concurrent_envs=8)


@app.middleware('http')
async def bounded_body(request,call_next):
    length=request.headers.get('content-length')
    if length and (not length.isdecimal() or len(length)>8 or int(length)>MAX_ACTION_BYTES+4096):
        return JSONResponse({'error':'request body too large'},status_code=413)
    if request.method in ('POST','PUT','PATCH'):
        chunks=[];size=0
        async for chunk in request.stream():
            size+=len(chunk)
            if size>MAX_ACTION_BYTES+4096:
                return JSONResponse({'error':'request body too large'},status_code=413)
            chunks.append(chunk)
        body=b''.join(chunks)
        # Starlette's downstream request receives exactly these bounded bytes.
        request._body=body
        if body:
            try:
                parse_json(body.decode('utf-8'))
            except (ValueError,UnicodeError,RecursionError):
                return JSONResponse({'error':'invalid bounded JSON'},status_code=400)
    return await call_next(request)


class BoundedWebSocketInput:
    def __init__(self,app):
        self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='websocket':
            return await self.app(scope,receive,send)
        async def bounded_receive():
            message=await receive()
            if message['type']=='websocket.receive':
                raw=message.get('text')
                try:
                    if raw is None: raise ValueError('text JSON required')
                    parse_json(raw)
                except (ValueError,RecursionError):
                    await send({'type':'websocket.close','code':1008})
                    return {'type':'websocket.disconnect','code':1008}
            return message
        return await self.app(scope,bounded_receive,send)


app.add_middleware(BoundedWebSocketInput)


def main():
    import uvicorn
    uvicorn.run(app,host='0.0.0.0',port=8000,ws_max_size=MAX_ACTION_BYTES+4096)


if __name__=='__main__':
    main()
