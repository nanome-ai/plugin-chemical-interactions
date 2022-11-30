# Modified version of this script:
# https://github.com/harryjubb/pdbtools/blob/master/clean_pdb.py

# Clean PDB Script
# ================
#
#
# PDB File Issues
# ---------------
#
# - Multiple models ** DONE **
# - Multiple occupancies/alternate locations  ** DONE **
#   - Pick highest occupancy, remove alternate locations  ** DONE **
#   - Set occupancies to 1.00  ** DONE **
# - Missing atoms, residues ** NOT DEALT WITH **
# - Chain breaks ** DONE **
#   - Output to file: or CA or N or C position ** DONE **
# - Selenomets to Mets ** DONE **
# - Nonstandard res to ATOM records ** DONE **

# IMPORTS
import argparse
import logging
import math
import operator
import os
import sys
import traceback
from functools import reduce
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from Bio.PDB import PDBParser
from Bio.PDB.Polypeptide import PPBuilder

from nanome.util import Logs

from .utils import chunks
# CONSTANTS
PDB_LINE_TEMPLATE = '{record: <6}{serial: >5} {atom_name: ^4}{altloc: ^1}{resname: ^3} {chain_id: ^1}{resnum: >4}{icode: ^1}   {x: >8.3f}{y: >8.3f}{z: >8.3f}{occ: >6.2f}{tfac: >6.2f}          {element: >2}{charge: >2}'    


def clean_pdb(pdb_path, plugin_instance=None, remove_waters=False, keep_hydrogens=True, informative_filenames=False):
    pdb_noext, pdb_ext = os.path.splitext(pdb_path)
    pdb_ext = pdb_ext.replace('.', '')

    pdb_parser = PDBParser(QUIET=True)
    struct_id = os.path.split(os.path.splitext(pdb_path)[0])[1]
    structure = pdb_parser.get_structure(struct_id, pdb_path)

    # OUTPUT LABEL
    output_label = 'clean'

    if informative_filenames:
        if remove_waters:
            output_label = output_label + '_dry'

        if keep_hydrogens:
            output_label = output_label + '_kh'

    # REMOVE MULTIPLE MODELS
    # BY TAKING THE FIRST MODEL
    model = structure[0]

    # RAISE AN ERROR FOR TOO MANY ATOMS
    if len(list(model.get_atoms())) > 99999:
        try:
            raise ValueError('More than 99999 atoms in the PDB model!')
        except Exception:
            traceback.print_exc(file=sys.stdout)
            exit(9)

    # DETERMINE POLYPEPTIDES AND CHAIN BREAKS
    ppb = PPBuilder()
    polypeptides = ppb.build_peptides(model, aa_only=False)

    # MAKE DATA STRUCTURES FOR CHAIN POLYPEPTIDES
    chain_ids = set([x.id for x in model.child_list])
    chain_pieces = OrderedDict()
    chain_polypeptides = OrderedDict()
    chain_break_residues = OrderedDict()
    chain_sequences = OrderedDict()

    for chain_id in chain_ids:
        chain_pieces[chain_id] = 0
        chain_break_residues[chain_id] = []
        chain_polypeptides[chain_id] = []

    # GET ALL POLYPEPTIDE RESIDUES IN THE MODEL
    polypeptide_residues = []

    for pp in polypeptides:
        for res in pp:
            polypeptide_residues.append(res)

    # GET THE CHAIN_ID(S) ASSOCIATED WITH EACH POLYPEPTIDE
    polypeptide_chain_id_sets = [set([k.get_parent().id for k in x]) for x in polypeptides]

    for e, polypeptide_chain_id_set in enumerate(polypeptide_chain_id_sets):
        # WARN IF NOT JUST ONE CHAIN ID ASSOCIATED WITH THE POLYPEPTIDE
        if len(polypeptide_chain_id_set) != 1:
            logging.warn('A polypeptide had {} chains associated with it: {}'.format(
                len(polypeptide_chain_id_set), polypeptide_chain_id_set))

        for polypeptide_chain_id in polypeptide_chain_id_set:
            chain_pieces[polypeptide_chain_id] = chain_pieces[polypeptide_chain_id] + 1
            # ADD FIRST AND LAST RESIDUE TO THE CHAIN BREAK RESIDUES (POLYPEPTIDE TERMINAL RESIDUES)
            chain_break_residues[polypeptide_chain_id] = chain_break_residues[polypeptide_chain_id] + [polypeptides[e][0], polypeptides[e][-1]]
            chain_polypeptides[polypeptide_chain_id] = chain_polypeptides[polypeptide_chain_id] + [polypeptides[e]]

    # POP OUT THE FIRST AND LAST RESIDUES FROM THE CHAIN BREAK RESIDUES
    # TO REMOVE THE GENUINE TERMINI
    for chain_id in chain_break_residues:
        chain_break_residues[chain_id] = chain_break_residues[chain_id][1:-1]

    # MAKE THE CHAIN SEQUENCES FROM THE CHAIN POLYPEPTIDE PIECES
    for chain_id in chain_polypeptides:
        pp_seqs = [str(x.get_sequence()) for x in chain_polypeptides[chain_id]]
        if pp_seqs:
            chain_sequences[chain_id] = reduce(operator.add, pp_seqs)

    # WRITE OUT CLEANED PDB
    # MANY OF THE ISSUES ARE SOLVED DURING THE WRITING OUT
    res_count = sum(1 for _ in model.get_residues())
    output_filepath = '.'.join((pdb_noext, output_label, pdb_ext))
    loading_bar_increment = math.ceil(res_count * 0.03)

    starting_atom_serial = 1
    output_lines = []

    residue_iter = model.get_residues()
    thread_count = max(res_count //  1000, 1)
    futs = []
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        for i, residue in enumerate(residue_iter):
            Logs.debug(f'Residue {i} / {res_count}: {residue}')
            if i % loading_bar_increment == 0 and plugin_instance:
                plugin_instance.menu.update_loading_bar(i, res_count)
            ending_atom_serial = starting_atom_serial + sum(1 for _ in residue.get_atoms())
            fut = executor.submit(clean_residue, residue, polypeptide_residues, remove_waters, keep_hydrogens, starting_atom_serial)
            futs.append(fut)
            starting_atom_serial = ending_atom_serial
    for fut in futs:
        residue_pdb_lines = fut.result()
        output_lines.extend(residue_pdb_lines)
    with open(output_filepath, 'w') as fo:
        for output_line in output_lines:
            fo.write(output_line)
            fo.write("\n")
    
    if plugin_instance:
        plugin_instance.menu.update_loading_bar(0, res_count)
    return output_filepath


def clean_residue(residue, polypeptide_residues, remove_waters, keep_hydrogens, atom_serial):
    # REMOVE WATERS IF FLAG SET
    if remove_waters:
        if residue.get_full_id()[3][0] == 'W':
            return

    record = 'ATOM'

    # SET HETATM RECORD IF IT WAS ORIGINALLY A HETATM OR WATER
    if residue.get_full_id()[3][0] == 'W' or residue.get_full_id()[3][0].startswith('H_'):
        record = 'HETATM'

    # SET ATOM RECORD IF THE RESIDUE IS IN A POLYPEPETIDE
    if residue in polypeptide_residues:
        record = 'ATOM'

    output_lines = []
    # LOOP THROUGH ATOMS TO OUTPUT
    for atom in residue.child_list:
        # DEAL WITH DISORDERED ATOMS
        if atom.is_disordered():
            atom = atom.disordered_get()

        # REMOVE HYDROGENS
        if not keep_hydrogens:
            if atom.element.strip() == 'H':
                continue

        # CONVERT SELENOMETHIONINES TO METHIONINES
        if residue in polypeptide_residues and (residue.resname == 'MSE' or residue.resname == 'MET'):
            residue.resname = 'MET'

            if atom.name == 'SE' and atom.element == 'SE':
                atom.name = 'SD'
                atom.element = 'S'

        # FIX ATOM NAME BUG
        if len(atom.name) == 3:
            atom.name = ' ' + atom.name

        # PDB OUTPUT
        # ATOM SERIALS ARE RENUMBERED FROM 1
        # ALTLOCS ARE ALWAYS BLANK
        # CHARGES ARE ALWAYS BLANK(?)
        # OCCUPANCIES ARE ALWAYS 1.00
        output_line = PDB_LINE_TEMPLATE.format(
            record=record,
            serial=atom_serial,
            atom_name=atom.name,
            altloc=' ',
            resname=residue.resname,
            chain_id=residue.get_parent().id,
            resnum=residue.get_id()[1],
            icode=residue.get_id()[2],
            x=float(atom.coord[0]),
            y=float(atom.coord[1]),
            z=float(atom.coord[2]),
            occ=1.00,
            tfac=atom.bfactor,
            element=atom.element,
            charge='')
        output_lines.append(output_line)
        atom_serial += 1
    return output_lines

# MAIN
if __name__ == '__main__':
    # ARGUMENT PARSING
    parser = argparse.ArgumentParser(description='''
        #############
        # CLEAN PDB #
        #############

        A program for cleaning PDB files.

        Dependencies:
        - Python > (v3.4)
        - BioPython (>= v1.60)

        ''', formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('pdb', type=str, help='Path to the PDB file to be cleaned.')
    parser.add_argument('-rmw', '--remove-waters', action='store_true', help='Remove waters.')
    parser.add_argument('-kh', '--keep-hydrogens', action='store_true', help='Keep hydrogens.')
    parser.add_argument('-if', '--informative_filenames', action='store_true', help='Keep a record of the flags used for cleaning the output filename.')

    args = parser.parse_args()

    pdb_path = args.pdb
    informative_filenames = args.informative_filenames
    remove_waters = args.remove_waters
    keep_hydrogens = args.keep_hydrogens
    clean_pdb(pdb_path, remove_waters, keep_hydrogens, informative_filenames)
