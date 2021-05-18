import os
import shutil

from flask import Flask, request, send_file

app = Flask(__name__)


@app.route('/', methods=['POST'])
def index():
    input_file = request.files['input_file']

    file_dir = '/var/output'
    try:
        os.mkdir(file_dir)
    except OSError:
        shutil.rmtree(file_dir)
        os.mkdir(file_dir)

    temp_filepath = '{}/{}'.format(file_dir, input_file.filename)
    input_file.save(temp_filepath)
    import pdb; pdb.set_trace()
    os.system('python clean_pdb.py -if {}'.format(temp_filepath))
    cleaned_filename = '{}.clean.pdb'.format(input_file.filename.split('.')[0])
    cleaned_file = '{}/{}'.format(file_dir, cleaned_filename)
    # Remove everything but the cleaned file:
    for filename in os.listdir(file_dir):
        if filename != cleaned_filename:
            os.remove('{}/{}'.format(file_dir, filename))

    # Set up and run arpeggio command
    flags = '-v '
    if 'atom_paths' in request.form:
        atom_paths = request.form['atom_paths'].split(',')
        for a_path in atom_paths:
            flags += '-s {} '.format(a_path)

    output_flag = ''  # '-op {}'.format(file_dir)
    command = 'python /arpeggio/arpeggio.py {} {} {}'.format(cleaned_file, flags, output_flag)
    import pdb; pdb.set_trace()

    os.system(command)

    import pdb; pdb.set_trace()

    # Zip output files, and send back to client
    file_list = os.listdir(file_dir)
    file_list.remove(cleaned_filename)
    zipfile = shutil.make_archive('/tmp/{}'.format(input_file.filename), 'zip', file_dir)
    return send_file(zipfile)


app.run(host='0.0.0.0', port=8000)
