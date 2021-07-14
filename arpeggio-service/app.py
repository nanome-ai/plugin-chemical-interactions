import json
import os

import subprocess
import tempfile
import uuid

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route('/clean', methods=['POST'])
def clean():
    # Assume only one file sent
    if len(request.files) != 1:
        raise Exception("Invalid data")

    input_file = next(request.files.values(), None)
    temp_dir = tempfile.mkdtemp()

    input_filename = input_file.filename
    data = ''
    with tempfile.TemporaryDirectory() as temp_dir:
        input_filepath = '{}/{}'.format(temp_dir, input_filename)
        input_file.save(input_filepath)
        subprocess.call(['python', 'clean_pdb.py', input_filepath])

        cleaned_filename = '{}.clean.pdb'.format(input_filename.split('.')[0])
        cleaned_filepath = '{}/{}'.format(temp_dir, cleaned_filename)

        with open(cleaned_filepath, 'r') as f:
            data = f.read()
    return data


@app.route('/', methods=['POST'])
def index():
    if len(request.files) != 1:
        raise Exception("Invalid data")

    input_file = next(request.files.values(), None)
    input_filename = input_file.filename

    output_data = {}
    with tempfile.TemporaryDirectory() as temp_dir:
        input_filepath = '{}/{}'.format(temp_dir, input_filename)
        input_file.save(input_filepath)

        # Set up and run arpeggio command
        arpeggio_path = '/opt/conda/bin/arpeggio'

        cmd = ['python', arpeggio_path, input_filepath]
        if 'selection' in request.form:
            selections = request.form['selection'].split(',')
            cmd.append('-s')
            cmd.extend(selections)

        # Create directory for output
        temp_uuid = uuid.uuid4()
        output_dir = f'{temp_dir}/{temp_uuid}'
        cmd.extend(['-o', output_dir])

        subprocess.call(cmd)

        try:
            output_filename = next(fname for fname in os.listdir(output_dir))
        except Exception:
            return {'error': 'Arpeggio call failed'}, 400

        output_filepath = f'{output_dir}/{output_filename}'
        with open(output_filepath, 'r') as f:
            output_data = json.load(f)
    return jsonify(output_data)
