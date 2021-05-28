import os
import shutil

from flask import Flask, request, send_file

app = Flask(__name__)


@app.route('/clean', methods=['POST'])
def clean():
    file_key = 'input_file.pdb'
    input_file = request.files[file_key]
    temp_dir = '/var/clean'
    try:
        os.mkdir(temp_dir)
    except OSError:
        shutil.rmtree(temp_dir)
        os.mkdir(temp_dir)

    input_filename = input_file.filename
    input_filepath = '{}/{}'.format(temp_dir, input_filename)
    input_file.save(input_filepath)
    os.system('python clean_pdb.py {}'.format(input_filepath))
    cleaned_filename = '{}.clean.pdb'.format(input_filename.split('.')[0])
    cleaned_filepath = '{}/{}'.format(temp_dir, cleaned_filename)

    data = ''
    with open(cleaned_filepath, 'r') as f:
        data = f.read()

    shutil.rmtree(temp_dir)
    return data


@app.route('/', methods=['POST'])
def index():
    file_key = 'input_file.pdb'
    input_file = request.files[file_key]
    temp_dir = '/var/calculate'

    try:
        os.mkdir(temp_dir)
    except OSError:
        shutil.rmtree(temp_dir)
        os.mkdir(temp_dir)

    input_filename = input_file.filename
    input_filepath = '{}/{}'.format(temp_dir, input_filename)
    input_file.save(input_filepath)

    # Set up and run arpeggio command
    flags = '-v '
    if 'selection' in request.form:
        selection = request.form['selection'].split(',')
        for sel in selection:
            flags += '-s {} '.format(sel)
    command = 'python /arpeggio/arpeggio.py {} {}'.format(input_filepath, flags)
    os.system(command)

    zipfile = shutil.make_archive('/tmp/{}'.format(input_filename), 'zip', temp_dir)
    shutil.rmtree(temp_dir)
    return send_file(zipfile)
