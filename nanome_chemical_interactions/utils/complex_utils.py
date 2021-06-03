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
            ComplexUtils.align_to(ligand, receptor)
            mol = next(combined_ligands.molecules)
            ligand_mol = list(ligand.molecules)[ligand.current_frame]
            for chain in ligand_mol.chains:
                mol.add_chain(chain)
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
            new_complex = complexes[i].convert_to_frames()
            new_complex.index = complexes[i].index
            complexes[i] = new_complex
    
    @staticmethod
    def convert_complex_to_frames(complex):
        new_complex = complex.convert_to_frames()
        new_complex.index = complex.index
        return new_complex

    @staticmethod
    def reset_transform(complex):
        complex.position = complex.old_position
        complex.rotation = complex.old_rotation
