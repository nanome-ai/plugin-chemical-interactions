import os
import shutil

from flask import Flask, request, send_file

app = Flask(__name__)


@app.route('/', methods=['POST'])
def index():
    input_file = request.files['input_file']
    temp_dir = '/var/output'

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

    # Remove everything but the cleaned file
    for filename in os.listdir(temp_dir):
        if filename != cleaned_filename:
            os.remove('{}/{}'.format(temp_dir, filename))
    os.system('mv {} {}'.format(cleaned_filepath, input_filepath))
    cleaned_filepath = input_filepath
    cleaned_filename = input_filename

    # Set up and run arpeggio command
    flags = '-v '
    if 'atom_paths' in request.form:
        atom_paths = request.form['atom_paths'].split(',')
        for a_path in atom_paths:
            flags += '-s {} '.format(a_path)

    command = 'python /arpeggio/arpeggio.py {} {}'.format(cleaned_filepath, flags)
    os.system(command)

    # Zip output files, and send back to client
    # file_list = os.listdir(temp_dir)
    # file_list.remove(cleaned_filename)
    zipfile = shutil.make_archive('/tmp/{}'.format(input_filename), 'zip', temp_dir)
    shutil.rmtree(temp_dir)
    return send_file(zipfile)


app.run(host='0.0.0.0', port=8000)
