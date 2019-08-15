#!/usr/bin/env python
# coding: utf-8
import argparse
import json

import flask
from flask_cors import CORS

parser = argparse.ArgumentParser()
parser.add_argument("--parser-ip", help="",
                    default='127.0.0.1')
parser.add_argument("--parser-port", help="",
                    default='1234')
args = parser.parse_args()

# initialize our Flask application and the Keras model
app = flask.Flask(__name__, template_folder='app')
# TODO check why CORS!?
CORS(app)


@app.route("/predict", methods=["POST"])
def predict():
    # initialize the data dictionary that will be returned from the
    # view
    data = {"success": False}

    # ensure an image was properly uploaded to our endpoint
    if flask.request.method == "POST":
        json_obj = flask.request.get_json()

        # TODO do something with the raw text
        data["text"] = json_obj['text']

        data = json.load(open('app/dummy.json', 'r'))

        # indicate that the request was a success
        data["success"] = True

    print(data)

    # return the data dictionary as a JSON response
    return flask.jsonify(data)


@app.route("/")
@app.route("/index")
def main():
    return flask.render_template('index.html', title='Home')


if __name__ == '__main__':
    app.run(debug=True)
