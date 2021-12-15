from argparse import ArgumentParser

import requests
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic.main import BaseModel
from pymongo import MongoClient

arg_parser = ArgumentParser()
arg_parser.add_argument("--root-path", default="", type=str, help="REST API hostname")
arg_parser.add_argument("--hostname", default="0.0.0.0", type=str, help="REST API hostname")
arg_parser.add_argument("--port", default=8080, type=int, help="REST API port")
arg_parser.add_argument("--bert-port", default=8081, type=int, help="REST API port")
arg_parser.add_argument("--limit", default=100, type=int, help="number of documents per corpus")
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


@app.get("/api/docs", tags=["api"])
async def get_documents(part: str = "gold"):
    db = MongoClient('localhost', 27017)['discopy']['docs']
    docs = db.find({'meta.part': part}, {'docID': 1})
    return [doc['docID'] for doc in docs]


@app.get("/api/docs/{doc_id}", tags=["api"])
async def get_document_by_id(doc_id: str, part: str = "gold"):
    db = MongoClient('localhost', 27017)['discopy']['docs']
    doc = db.find_one({'meta.part': part, 'docID': doc_id})
    if doc:
        for sent in doc['sentences']:
            sent['words'] = [(simple_map.get(t[0], t[0]), t[1]) for t in sent['words']]
        return doc


@app.get("/api/corpora", tags=["api"])
async def get_corpora():
    db = MongoClient('localhost', 27017)['discopy']['docs']
    return {
        'pred': [{'corpus': i['_id'], 'count': i['count']} for i in db.aggregate(
            [{'$match': {'meta.part': 'pred'}}, {'$group': {'_id': '$meta.corpus', 'count': {'$sum': 1}}}])],
        'gold': [{'corpus': i['_id'], 'count': i['count']} for i in db.aggregate(
            [{'$match': {'meta.part': 'gold'}}, {'$group': {'_id': '$meta.corpus', 'count': {'$sum': 1}}}])]
    }


@app.get("/api/sentences/{doc_id}", tags=["api"])
async def get_sentences_by_id(doc_id: str, part: str = "gold"):
    doc = await get_document_by_id(doc_id, part)
    if doc:
        return doc['sentences']


def prepare_relation(rel, words):
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
    return r


@app.get("/api/relations/{doc_id}", tags=["api"])
async def get_relations_by_id(doc_id: str, part: str = "gold"):
    relations = []
    doc = await get_document_by_id(doc_id, part)
    if doc:
        words = [w[0] for s in doc['sentences'] for w in s["words"]]
        for rel in doc['relations']:
            relations.append(prepare_relation(rel, words))
        return relations


class ParserRequest(BaseModel):
    text: str


@app.post("/api/parser")
def apply_parser(r: ParserRequest):
    db = MongoClient('localhost', 27017)['discopy']['requests']
    r = requests.post(f'http://localhost:{args.bert_port}/api/parser', json={
        'text': r.text,
    })
    if r.status_code == 200:
        doc = r.json()
        db.insert_one(doc)
        relations = []
        words = [w[0] for s in doc['sentences'] for w in s["words"]]
        for rel in doc['relations']:
            relations.append(prepare_relation(rel, words))
        return relations
    else:
        return 404


@app.get("/", tags=["templates"], response_class=HTMLResponse)
@app.get("/index", tags=["templates"], response_class=HTMLResponse)
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
    uvicorn.run("run:app", host=args.hostname, port=args.port, log_level="debug", reload=args.reload,
                root_path=args.root_path)
