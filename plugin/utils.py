from itertools import chain
from nanome.api import structure
from nanome.api.interactions import Interaction
from nanome.util import ComplexUtils, Vector3
from nanome.util.enums import InteractionKind
from scipy.spatial import KDTree


__all__ = ['chunks', 'extract_residues_from_complex', 'merge_complexes']


def extract_residues_from_complex(comp, residue_list, comp_name=None):
    """Copy comp, and remove all residues that are not part of the binding site."""
    new_comp = structure.Complex()
    new_mol = structure.Molecule()
    new_comp.add_molecule(new_mol)
    new_comp.name = comp_name or f'{comp.name}'
    new_comp.index = -1
    new_comp.position = comp.position
    new_comp.rotation = comp.rotation

    binding_site_residue_indices = [r.index for r in residue_list]
    for ch in comp.chains:
        reses_on_chain = [res for res in ch.residues if res.index in binding_site_residue_indices]
        if reses_on_chain:
            new_ch = structure.Chain()
            new_ch.name = ch.name
            new_ch.residues = reses_on_chain
            new_mol.add_chain(new_ch)
    return new_comp


def get_neighboring_atoms(target_reference: structure.Complex, selected_atoms: list, site_size=6):
    """Use KDTree to find target atoms within site_size radius of selected atoms."""
    mol = next(
        mol for i, mol in enumerate(target_reference.molecules)
        if i == target_reference.current_frame)
    ligand_positions = [atom.position.unpack() for atom in selected_atoms]
    target_atoms = chain(*[ch.atoms for ch in mol.chains if not ch.name.startswith("H")])
    target_tree = KDTree([atom.position.unpack() for atom in target_atoms])
    target_point_indices = target_tree.query_ball_point(ligand_positions, site_size)
    near_point_set = set()
    for point_indices in target_point_indices:
        for point_index in point_indices:
            near_point_set.add(tuple(target_tree.data[point_index]))
    neighbor_atoms = []
    for targ_atom in mol.atoms:
        if targ_atom.position.unpack() in near_point_set:
            neighbor_atoms.append(targ_atom)
    return neighbor_atoms


def merge_complexes(complexes, align_reference, selected_atoms_only=False):
    """Merge a list of Complexes into one Complex.

    complexes: list of complexes to merge
    align_reference: Complex to align other complexes to.
    target: Complex to merge into. If None, a new Complex is created.
    """
    # Copy list so that conformer modifications aren't propogated.
    comp_copies = [cmp._deep_copy() for cmp in complexes]
    # Fix indices
    for original, cpy in zip(complexes, comp_copies):
        cpy.index = original.index

    merged_complex = structure.Complex()
    mol = structure.Molecule()
    merged_complex.add_molecule(mol)
    for comp in comp_copies:
        ComplexUtils.align_to(comp, align_reference)
        # Only return current conformer
        existing_mol = next(mol for i, mol in enumerate(comp.molecules) if i == comp.current_frame)
        # Extract only the current conformer from the molecule
        existing_mol.move_conformer(existing_mol.current_conformer, 0)
        existing_mol.set_conformer_count(1)

        if selected_atoms_only and comp.index != align_reference.index:
            # Extract selected copy selected residues
            selected_residues = [res for res in existing_mol.residues if any(a.selected for a in res.atoms)]
            extracted_comp = extract_residues_from_complex(comp, selected_residues)
            for ch in extracted_comp.chains:
                mol.add_chain(ch)
        else:
            for ch in existing_mol.chains:
                mol.add_chain(ch)
    return merged_complex


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# Maps the interaction type format from Arpeggio, to the InteractionKind enum.
interaction_type_map = {
    'covalent': InteractionKind.Covalent,
    'hbond': InteractionKind.HydrogenBond,
    'ionic': InteractionKind.Ionic,
    'xbond': InteractionKind.XBond,
    'metal_complex': InteractionKind.MetalComplex,
    'aromatic': InteractionKind.Aromatic,
    'hydrophobic': InteractionKind.Hydrophobic,
    'vdw': InteractionKind.VanDerWall,
    'vdw_clash': InteractionKind.VanDerWallClash,
    'weak_hbond': InteractionKind.WeakHBond,
    'polar': InteractionKind.Polar,
    'weak_polar': InteractionKind.WeakPolar,
    'clash': InteractionKind.Clash,
    'carbonyl': InteractionKind.Carbonyl,
    'CARBONPI': InteractionKind.CarbonPi,
    'CATIONPI': InteractionKind.CationPi,
    'DONORPI': InteractionKind.DonorPi,
    'HALOGENPI': InteractionKind.HalogenPi,
    'METSULPHURPI': InteractionKind.MetsulphurPi,
    'proximal': InteractionKind.Proximal,
}


def centroid(atoms):
    """Calculate center of the group of atoms."""
    coords = [a.position.unpack() for a in atoms]
    sum_x = sum([vec[0] for vec in coords])
    sum_y = sum([vec[1] for vec in coords])
    sum_z = sum([vec[2] for vec in coords])
    len_coord = len(coords)
    centroid = Vector3(sum_x / len_coord, sum_y / len_coord, sum_z / len_coord)
    return centroid


def calculate_interaction_length(line: Interaction, complexes):
    """Determine length of line using the distance between the structures."""
    all_atoms = chain(*[comp.atoms for comp in complexes])
    struct1_atoms = []
    struct2_atoms = []
    for atom in all_atoms:
        if str(atom.index) in line.atom1_idx_arr:
            struct1_atoms.append(atom)
        if str(atom.index) in line.atom2_idx_arr:
            struct2_atoms.append(atom)
    struct1_centroid = centroid(struct1_atoms)
    struct2_centroid = centroid(struct2_atoms)
    distance = Vector3.distance(struct1_centroid, struct2_centroid)
    return distance


def line_in_frame(line: Interaction, complexes):
    """Return boolean stating whether both structures connected by line are in frame.

    :arg line: Line object. The line in question.
    :arg complexes: List of complexes in workspace that can contain atoms.
    """
    all_atoms = chain(*[comp.atoms for comp in complexes])
    # Find the atoms from the comp by their id, and make sure  they're in the same conformer.
    atom1_in_frame = None
    atom2_in_frame = None
    for atom in all_atoms:
        if atom.index in line.atom1_idx_arr:
            mol = atom.molecule
            atom1_in_frame = mol.current_conformer == line.atom1_conformation
        elif atom.index in line.atom2_idx_arr:
            mol = atom.molecule
            atom2_in_frame = mol.current_conformer == line.atom2_conformation
        if atom1_in_frame is not None and atom2_in_frame is not None:
            break

    line_in_frame = atom1_in_frame and atom2_in_frame
    return line_in_frame
