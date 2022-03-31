from nanome.api import structure
from nanome.util import ComplexUtils


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
