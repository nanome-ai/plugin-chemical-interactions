import nanome


class ComplexUtils:

    @staticmethod
    def align_to(complex, reference_complex):
        m = complex.get_complex_to_workspace_matrix()
        for atom in complex.atoms:
            atom.position = m * atom.position
        complex.old_position = complex.position
        complex.old_rotation = complex.rotation
        complex.position = reference_complex.position
        complex.rotation = reference_complex.rotation
        m = complex.get_workspace_to_complex_matrix()
        for atom in complex.atoms:
            atom.position = m * atom.position

    @staticmethod
    def combine_ligands(receptor, ligands, target=None):
        combined_ligands = target or nanome.structure.Complex()
        for ligand in ligands:
            # selected_nanome_residue = next(res for res in ligand.residues if str(res._serial) == str(selected_ligand.id[1]))
            ComplexUtils.align_to(ligand, receptor)

            ligand_chain = next(ligand.chains)
            mol = next(combined_ligands.molecules)
            mol.add_chain(ligand_chain)
        return combined_ligands

    @staticmethod
    def convert_to_conformers(complexes):
        for i in range(len(complexes)):
            complex_index = complexes[i].index
            complexes[i] = complexes[i].convert_to_conformers()
            complexes[i].index = complex_index

    @staticmethod
    def convert_to_frames(complexes):
        for i in range(len(complexes)):
            complex_index = complexes[i].index
            complexes[i] = complexes[i].convert_to_frames()
            complexes[i].index = complex_index

    @staticmethod
    def reset_transform(complex):
        complex.position = complex.old_position
        complex.rotation = complex.old_rotation
