# Thank you harryjubb for this beautiful tool
import os

from Bio.PDB import PDBParser
from Bio.PDB import NeighborSearch
from Bio.PDB.Polypeptide import PPBuilder

from numpy.linalg import norm

# CONSTANTS
COVALENT_RADII = {
    'H': 0.31, 'HE': 0.28, 'LI': 1.28, 'BE': 0.96, 'B': 0.84, 'C': 0.76, 'N': 0.71, 'O': 0.66, 'F': 0.57, 'NE': 0.58, 'NA': 1.66,
    'MG': 1.41, 'AL': 1.21, 'SI': 1.11, 'P': 1.07, 'S': 1.05, 'CL': 1.02, 'AR': 1.06, 'K': 2.03, 'CA': 1.76, 'SC': 1.7, 'TI': 1.6,
    'V': 1.53, 'CR': 1.39, 'MN': 1.39, 'FE': 1.32, 'CO': 1.26, 'NI': 1.24, 'CU': 1.32, 'ZN': 1.22, 'GA': 1.22, 'GE': 1.2, 'AS': 1.19,
    'SE': 1.2, 'BR': 1.2, 'KR': 1.16, 'RB': 2.2, 'SR': 1.95, 'Y': 1.9, 'ZR': 1.75, 'NB': 1.64, 'MO': 1.54, 'TC': 1.47, 'RU': 1.46,
    'RH': 1.42, 'PD': 1.39, 'AG': 1.45, 'CD': 1.44, 'IN': 1.42, 'SN': 1.39, 'SB': 1.39, 'TE': 1.38, 'I': 1.39, 'XE': 1.4, 'CS': 2.44,
    'BA': 2.15, 'LA': 2.07, 'CE': 2.04, 'PR': 2.03, 'ND': 2.01, 'PM': 1.99, 'SM': 1.98, 'EU': 1.98, 'GD': 1.96, 'TB': 1.94, 'DY': 1.92,
    'HO': 1.92, 'ER': 1.89, 'TM': 1.9, 'YB': 1.87, 'LU': 1.87, 'HF': 1.75, 'TA': 1.7, 'W': 1.62, 'RE': 1.51, 'OS': 1.44, 'IR': 1.41,
    'PT': 1.36, 'AU': 1.36, 'HG': 1.32, 'TL': 1.45, 'PB': 1.46, 'BI': 1.48, 'PO': 1.4, 'AT': 1.5, 'RN': 1.5, 'FR': 2.6, 'RA': 2.21,
    'AC': 2.15, 'TH': 2.06, 'PA': 2.0, 'U': 1.96, 'NP': 1.9, 'PU': 1.87, 'AM': 1.8, 'CM': 1.69, 'BK': 1.6, 'CF': 1.6, 'ES': 1.6,
    'FM': 1.6, 'MD': 1.6, 'NO': 1.6, 'LR': 1.6, 'RF': 1.6, 'DB': 1.6, 'SG': 1.6, 'BH': 1.6, 'HS': 1.6, 'MT': 1.6, 'DS': 1.6, 'RG': 1.6,
    'CN': 1.6, 'UUT': 1.6, 'FL': 1.6, 'UUP': 1.6, 'LV': 1.6, 'UUH': 1.6, 'UUH': 1.6
}

MAX_COV_RADIUS = max(COVALENT_RADII.values())
MAX_COV_BOND = MAX_COV_RADIUS * 2


def ligands(pdb_tempfile):
    # LOAD THE PDB
    pdb_parser = PDBParser()
    id = os.path.split(os.path.splitext(pdb_tempfile.name)[0])[1]
    fl = pdb_tempfile.name
    structure = pdb_parser.get_structure(id, fl)

    # EXTRACT THE MODEL
    model = structure[0]

    # ASSIGN COVALENT RADII
    for atom in model.get_atoms():
        try:
            atom.covrad = COVALENT_RADII[atom.element.strip().upper()]
        except Exception:
            print(f'Covalent radius could not be determined for atom {atom}')

    # DETERMINE POLYPEPTIDES AND CHAIN BREAKS
    ppb = PPBuilder()
    polypeptides = ppb.build_peptides(model, aa_only=False)

    # GET ALL POLYPEPTIDE RESIDUES IN THE MODEL
    polypeptide_residues = set([])

    for polypeptide in polypeptides:
        for residue in polypeptide:
            polypeptide_residues.add(residue)

    # GET NON-POLYPEPTIDE HETEROATOM RESIDUES
    heteroresidues = [r for r in model.get_residues() if 'H_' in r.get_full_id()[3][0] and r not in polypeptide_residues]

    # DISCARD COVALENTLY BOUND RESIDUES
    ns = NeighborSearch(list(model.get_atoms()))
    non_cov_heteroresidues = []
    for residue in heteroresidues:
        residue_is_cov = False
        for atom in residue.child_list:
            nearby_atoms = ns.search(atom.coord, MAX_COV_BOND)
            if nearby_atoms:
                for nearby_atom in nearby_atoms:
                    # NO SELFIES! OFC THE ATOM WILL COV-BOND IN IT'S OWN RESIDUE...
                    if nearby_atom in residue.child_list:
                        continue

                    sum_cov_radii = atom.covrad + nearby_atom.covrad
                    distance = norm(atom.coord - nearby_atom.coord)

                    if distance <= sum_cov_radii:

                        # print atom, nearby_atom, sum_cov_radii, distance
                        residue_is_cov = True
                        break

            if residue_is_cov:
                break

        if not residue_is_cov:
            non_cov_heteroresidues.append(residue)

    # LIMIT TO > 7 HEAVY ATOM LIGANDS
    return [r for r in non_cov_heteroresidues if len(r.child_list) > 7]
