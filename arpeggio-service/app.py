import os
import shutil
import tempfile

from flask import Flask, request, send_file

app = Flask(__name__)


@app.route('/', methods=['POST'])
def index():
    input_file = request.files['input_file']
    import pdb;pdb.set_trace()

    file_dir = '/var/output'
    os.mkdir(file_dir)
    temp_filepath = '{}/{}.pdb'.format(file_dir, input_file.filename)
    input_file.save(temp_filepath)

    os.system('python clean_pdb.py -if {}'.format(temp_filepath))
    cleaned_file = '{}/input_file.clean.pdb'.format(file_dir)

    # Set up and run arpeggio command
    atom_paths = request.form['atom_paths'].split(',')
    flags = '-v '
    for a_path in atom_paths:
        flags += '-s {} '.format(a_path)

    # flags = '-s RESNAME:FMM -v'
    output_flag = '-op {}'.format(file_dir)
    command = 'python /arpeggio/arpeggio.py {} {} {}'.format(cleaned_file, flags, output_flag)
    import pdb; pdb.set_trace()

    os.system(command)

    import pdb; pdb.set_trace()
    # Zip output files, and send back to client
    file_list = os.listdir(temp_dir)
    # file_list.remove(input_file.filename)
    zipfile = shutil.make_archive('/tmp/{}'.format(input_file.filename), 'zip', temp_dir)
    return send_file(zipfile)


app.run(host='0.0.0.0', port=8000)
