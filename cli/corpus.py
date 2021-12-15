import json

import click
from pymongo import MongoClient
from tqdm import tqdm


@click.command()
@click.argument('part')
@click.option('-i', '--src', default='-', type=click.File('r'))
@click.option('-l', '--limit', default=0, type=int)
@click.option('-d', '--drop', is_flag=True)
def main(part, src, limit, drop):
    client = MongoClient('localhost', 27017)
    db = client['discopy']['docs']
    if drop:
        db.drop()
        db.create_index([('docID', 1), ('part', 1)], name='document_idx')
        db.create_index([('meta.corpus', 1)], name='corpus_idx')
    for line_i, line in tqdm(enumerate(src)):
        if limit and line_i >= limit:
            break
        doc_json = json.loads(line)
        if 'meta' not in doc_json:
            doc_json['meta'] = {'part': part}
        else:
            doc_json['meta']['part'] = part
        db.insert_one(doc_json)
    client.close()


if __name__ == '__main__':
    main()
