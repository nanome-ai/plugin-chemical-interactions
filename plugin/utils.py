from nanome.api import structure
from nanome.util import ComplexUtils


__all__ = ['extract_residues', 'merge_complexes']


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


def merge_complexes(complexes, align_reference):
    """Merge a list of Complexes into one Complex.
    complexes: list of complexes to merge
    align_reference: Complex to align other complexes to.
    target: Complex to merge into. If None, a new Complex is created.
    """
    combined_ligands = structure.Complex()
    mol = structure.Molecule()
    combined_ligands.add_molecule(mol)
    mol = list(combined_ligands.molecules)[combined_ligands.current_frame]
    for comp in complexes:
        ComplexUtils.align_to(comp, align_reference)
        ligand_mol = next(mol for i, mol in enumerate(comp.molecules) if i == comp.current_frame)
        for chain in ligand_mol.chains:
            mol.add_chain(chain)
    return combined_ligands
