import bz2
import glob
import ujson as json
import os
from argparse import ArgumentParser
from collections import defaultdict

import requests
import uvicorn
from typing import Optional
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic.main import BaseModel

arg_parser = ArgumentParser()
arg_parser.add_argument("--hostname", default="0.0.0.0", type=str, help="REST API hostname")
arg_parser.add_argument("--port", default=8080, type=int, help="REST API port")
arg_parser.add_argument("--data", default='data', type=str, help="path to corpora")
arg_parser.add_argument("--reload", action="store_true", help="Reload service on file changes")
args = arg_parser.parse_args()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

simple_map = {
    "''": '"',
    "``": '"',
    "-LRB-": "(",
    "-RRB-": ")",
    "-LCB-": "{",
    "-RCB-": "}",
    "n't": "not"
}

DOCS = defaultdict(dict)
PARSES = defaultdict(dict)


# TOKENS = {
#     "abc1223": "rene.knaebel"
# }
#
#
# async def user_access_token(access_token: Optional[str] = None):
#     if access_token in TOKENS:
#         return TOKENS[access_token]
#     else:
#         raise HTTPException(status_code=404, detail="Invalid Access Token")
#
#
# @app.get("/api/docs", tags=["api"])
# async def get_documents(user: str = Depends(user_access_token)):
#     print(user)
#     r = requests.get('http://localhost:5000/api/docs')
#     if r.status_code == 200:
#         return r.json()

@app.on_event("startup")
async def startup_event():
    global DOCS, PARSES
    for corpus in glob.glob(os.path.join(args.data, 'gold') + '/*.json.bz2'):
        print("Load corpus:", corpus)
        with bz2.open(corpus) as fh:
            for line in fh:
                doc = json.loads(line)
                DOCS[doc['docID']] = doc
    for corpus in glob.glob(os.path.join(args.data, 'parsed') + '/*.json.bz2'):
        print("Load corpus:", corpus)
        with bz2.open(corpus) as fh:
            for line in fh:
                doc = json.loads(line)
                PARSES[doc['docID']] = doc
    print('Corpus loading done...')


@app.get("/api/docs/gold", tags=["api"])
async def get_gold_documents():
    return [doc_id for doc_id in DOCS.keys()]


@app.get("/api/docs/pred", tags=["api"])
async def get_pred_documents():
    return [doc_id for doc_id in PARSES.keys()]


@app.get("/api/docs/gold/{doc_id}", tags=["api"])
async def get_document_gold_by_id(doc_id: str):
    if doc_id in DOCS:
        doc = DOCS[doc_id]
        for sent in doc['sentences']:
            sent['words'] = [(simple_map.get(t[0], t[0]), t[1]) for t in sent['words']]
        return doc


def get_document_by_id(doc_id, corpus):
    if doc_id in corpus:
        doc = corpus[doc_id]
        for sent in doc['sentences']:
            sent['words'] = [(simple_map.get(t[0], t[0]), t[1]) for t in sent['words']]
        return doc


@app.get("/api/docs/pred/{doc_id}", tags=["api"])
async def get_document_pred_by_id(doc_id: str):
    return get_document_by_id(doc_id, PARSES)


@app.get("/api/sentences/gold/{doc_id}", tags=["api"])
async def get_sentences_by_id(doc_id: str):
    doc = await get_document_gold_by_id(doc_id)
    if doc:
        return doc['sentences']


@app.get("/api/sentences/pred/{doc_id}", tags=["api"])
async def get_sentences_by_id(doc_id: str):
    doc = await get_document_pred_by_id(doc_id)
    if doc:
        return doc['sentences']


@app.get("/api/relations/gold/{doc_id}", tags=["api"])
async def get_relations_by_id(doc_id: str):
    relations = []
    doc = await get_document_gold_by_id(doc_id)
    if doc:
        words = [w[0] for s in doc['sentences'] for w in s["words"]]
        for rel in doc['relations']:
            arg1 = {i[2] for i in rel['Arg1']['TokenList']}
            arg2 = {i[2] for i in rel['Arg2']['TokenList']}
            conn = {i[2] for i in rel['Connective']['TokenList']}
            min_pos = min(arg1 | arg2 | conn)
            max_pos = max(arg1 | arg2 | conn)
            tokens = [{
                'surface': simple_map.get(w, w),
                'class': "Arg1" if i in arg1 else "Arg2" if i in arg2 else "Conn" if i in conn else ""
            } for i, w in enumerate(words)][max(min_pos - 10, 0):min(max_pos + 11, len(words))]
            tmp = tokens[:1]
            for t in tokens[1:]:
                if t['class'] == tmp[-1]['class']:
                    tmp[-1]['surface'] += ' ' + t['surface']
                else:
                    tmp.append(t)
            r = {
                'type': rel['Type'],
                'sense': rel['Sense'][0],
                'tokens': tmp,
            }
            relations.append(r)
        return relations


@app.get("/api/relations/pred/{doc_id}", tags=["api"])
async def get_relations_pred_by_id(doc_id: str):
    relations = []
    doc = await get_document_pred_by_id(doc_id)
    if doc:
        words = [w[0] for s in doc['sentences'] for w in s["words"]]
        for rel in doc['relations']:
            arg1 = {i[2] for i in rel['Arg1']['TokenList']}
            arg2 = {i[2] for i in rel['Arg2']['TokenList']}
            conn = {i[2] for i in rel['Connective']['TokenList']}
            min_pos = min(arg1 | arg2 | conn)
            max_pos = max(arg1 | arg2 | conn)
            tokens = [{
                'surface': simple_map.get(w, w),
                'class': "Arg1" if i in arg1 else "Arg2" if i in arg2 else "Conn" if i in conn else ""
            } for i, w in enumerate(words)][max(min_pos - 10, 0):min(max_pos + 11, len(words))]
            tmp = tokens[:1]
            for t in tokens[1:]:
                if t['class'] == tmp[-1]['class']:
                    tmp[-1]['surface'] += ' ' + t['surface']
                else:
                    tmp.append(t)
            r = {
                'type': rel['Type'],
                'sense': rel['Sense'][0],
                'tokens': tmp,
            }
            relations.append(r)
        return relations


class ParserRequest(BaseModel):
    text: str


@app.post("/api/parser")
def apply_parser(r: ParserRequest):
    r = requests.post('http://localhost:5000/api/parser', json={
        'text': r.text,
    })
    if r.status_code == 200:
        doc = r.json()
        relations = []
        words = [w[0] for s in doc['sentences'] for w in s["words"]]
        for rel in doc['relations']:
            arg1 = {i[2] for i in rel['Arg1']['TokenList']}
            arg2 = {i[2] for i in rel['Arg2']['TokenList']}
            conn = {i[2] for i in rel['Connective']['TokenList']}
            min_pos = min(arg1 | arg2 | conn)
            max_pos = max(arg1 | arg2 | conn)
            tokens = [{
                'surface': simple_map.get(w, w),
                'class': "Arg1" if i in arg1 else "Arg2" if i in arg2 else "Conn" if i in conn else ""
            } for i, w in enumerate(words)][max(min_pos - 10, 0):min(max_pos + 11, len(words))]
            tmp = tokens[:1]
            for t in tokens[1:]:
                if t['class'] == tmp[-1]['class']:
                    tmp[-1]['surface'] += ' ' + t['surface']
                else:
                    tmp.append(t)
            r = {
                'type': rel['Type'],
                'sense': rel['Sense'][0],
                'tokens': tmp,
            }
            relations.append(r)
        return relations
    else:
        return 404


@app.get("/", tags=["templates"], response_class=HTMLResponse)
async def get_main_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/view", tags=["templates"], response_class=HTMLResponse)
async def get_view_page(request: Request):
    return templates.TemplateResponse("view.html", {"request": request})


@app.get("/parser-view", tags=["templates"], response_class=HTMLResponse)
async def get_parser_view_page(request: Request):
    return templates.TemplateResponse("parser_view.html", {"request": request})


@app.get("/parser", tags=["templates"], response_class=HTMLResponse)
async def get_parser_page(request: Request):
    return templates.TemplateResponse("parser.html", {"request": request})


if __name__ == '__main__':
    uvicorn.run("run:app", host=args.hostname, port=args.port, log_level="debug", reload=args.reload)
