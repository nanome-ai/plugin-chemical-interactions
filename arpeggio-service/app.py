import subprocess
import shutil
import tempfile

from flask import Flask, request, send_file

app = Flask(__name__)


@app.route('/clean', methods=['POST'])
def clean():
    # Assume only one file sent
    if len(request.files) != 1:
        raise Exception("Invalid data")

    input_file = request.files.values()[0]
    input_filename = input_file.filename
    temp_dir = tempfile.mkdtemp()
    try:
        input_filepath = '{}/{}'.format(temp_dir, input_filename)
        input_file.save(input_filepath)
        subprocess.call(['python', 'clean_pdb.py', input_filepath])

        cleaned_filename = '{}.clean.pdb'.format(input_filename.split('.')[0])
        cleaned_filepath = '{}/{}'.format(temp_dir, cleaned_filename)

        data = ''
        with open(cleaned_filepath, 'r') as f:
            data = f.read()
    except:
        shutil.rmtree(temp_dir)
    else:
        shutil.rmtree(temp_dir)
    return data


@app.route('/', methods=['POST'])
def index():
    if len(request.files) != 1:
        raise Exception("Invalid data")

    input_file = request.files.values()[0]
    input_filename = input_file.filename
    temp_dir = tempfile.mkdtemp()
    try:
        input_filepath = '{}/{}'.format(temp_dir, input_filename)
        input_file.save(input_filepath)
        # Set up and run arpeggio command
        arpeggio_path = '/arpeggio/arpeggio.py'

        cmd = ['python', arpeggio_path, input_filepath, '-v']
        if 'selection' in request.form:
            selections = request.form['selection'].split(',')
            cmd.append('-s')
            cmd.extend(selections)
        print(cmd)
        subprocess.call(cmd)
        zipfile = shutil.make_archive('/tmp/{}'.format(input_filename), 'zip', temp_dir)
    except:
        shutil.rmtree(temp_dir)
    else:
        shutil.rmtree(temp_dir)
    return send_file(zipfile)
