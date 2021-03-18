import os

from discopy.components.altlex.bert_linear import DiscourseSignalExtractor
from discopy.data.loaders.conll import load_bert_conll_dataset
from discopy.parsers.pipeline import ParserPipeline
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

CONLL_PATH = os.environ.get('DISCOPY_CONLL_PATH')
BERT_MODEL = os.environ.get('DISCOPY_BERT_MODEL')
data = {}
parser = None


@app.on_event("startup")
async def startup_event():
    global data, parser
    # data['train'] = load_bert_conll_dataset(os.path.join(CONLL_PATH, 'en.train'),
    #                                         simple_connectives=False,
    #                                         cache_dir=os.path.join(CONLL_PATH, f'en.train.{BERT_MODEL}.joblib'),
    #                                         bert_model=BERT_MODEL)
    for part in ['dev', 'test']:
        docs = load_bert_conll_dataset(os.path.join(CONLL_PATH, f'en.{part}'),
                                       simple_connectives=False,
                                       cache_dir=os.path.join(CONLL_PATH, f'en.{part}.{BERT_MODEL}.joblib'),
                                       bert_model=BERT_MODEL)
        for doc in docs:
            data[doc.doc_id] = doc
    clf = DiscourseSignalExtractor(window_length=150, input_dim=doc.get_embedding_dim(), hidden_dim=128,
                                   rnn_dim=256, step_size=1, ckpt_path='models/altlex')
    clf.load('/project/discopy/models/nn')
    parser = ParserPipeline([clf])


@app.get("/api/documents", tags=["api"])
async def get_documents():
    return [doc_id for doc_id in data]


@app.get("/api/document/{doc_id}", tags=["api"])
def get_document_by_id(doc_id: str):
    global parser
    if doc_id in data:
        doc = data.get(doc_id)
        conns_original = {t.idx for rel in doc.relations for t in rel.conn.tokens}
        doc = parser(doc)
        conns = {t.idx for rel in doc.relations for t in rel.conn.tokens}

        def highlight(surface, idx):
            if idx in conns:
                surface = f"<b>{surface}</b>"
            if idx in conns_original:
                surface = f"<mark>{surface}</mark>"
            return surface

        sentences = [[(s.tokens[0].surface, s.tokens[0].idx)] +
                     [(('' if s.tokens[t_i].offset_end == t.offset_begin else ' ') + t.surface, t.idx)
                      for t_i, t in enumerate(s.tokens[1:])] for s in doc.sentences]
        doc.text = ''.join([highlight(surface, idx) for s in sentences for surface, idx in s])
        return doc.to_json()
    raise FileNotFoundError("No document with id found.")


@app.get("/", tags=["templates"], response_class=HTMLResponse)
async def main(request: Request):
    return templates.TemplateResponse("altlex.html", {"request": request})
