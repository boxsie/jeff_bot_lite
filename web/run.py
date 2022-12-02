#!/usr/bin/env python3
import os
import argparse

from flask import Flask
from flask_cors import CORS
from waitress import serve

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return app.send_static_file('index.html')

if __name__ == "__main__":
    serve(app, host='0.0.0.0', port=5000)
