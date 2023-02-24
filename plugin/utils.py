from itertools import chain
from nanome.api import structure
from nanome.util import ComplexUtils
from scipy.spatial import KDTree


__all__ = ['chunks', 'extract_residues', 'merge_complexes']


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
    merged_complex = structure.Complex()
    mol = structure.Molecule()
    merged_complex.add_molecule(mol)
    for comp in complexes:
        ComplexUtils.align_to(comp, align_reference)
        # Only return current conformer
        if len(list(comp.molecules)) > 1:
            existing_mol = next(mol for i, mol in enumerate(comp.molecules) if i == comp.current_frame)
        else:
            # Extract only the current conformer from the molecule
            existing_mol = next(comp.molecules)
            existing_mol.move_conformer(existing_mol.current_conformer, 0)
            existing_mol.set_conformer_count(1)

        if selected_atoms_only and comp.index != align_reference.index:
            # Extract selected copy selected residues
            selected_residues = [res for res in comp.residues if any(a.selected for a in res.atoms)]
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
