import bpy
import numpy as np
from .tools import coll_mn
import warnings
from . import data
from . import assembly
from . import nodes
from .assembly import mmtf

def molecule_rcsb(pdb_code, 
                  center_molecule=False, 
                  del_solvent=True, 
                  include_bonds=True, 
                  starting_style=0, 
                  setup_nodes=True
                  ):
    
    mol, file = open_structure_rcsb(pdb_code = pdb_code, include_bonds=include_bonds)
    mol_object, coll_frames = create_molecule(
        mol_array = mol,
        mol_name = pdb_code,
        center_molecule = center_molecule,
        del_solvent = del_solvent, 
        include_bonds = include_bonds
        )
    
    if setup_nodes:
        nodes.create_starting_node_tree(
            obj = mol_object, 
            coll_frames=coll_frames, 
            starting_style = starting_style
            )
    
    # TODO support more than a single assembly
    # TODO support chain selections for the assemblies
    assemblies = mmtf.MMTFAssemblyParser(file).get_transformations("1")
    assemblies = [(sym[0].copy(order='c'), sym[1].copy(order='c'), sym[2].copy(order='c')) for sym in assemblies]
    mol_object['bio_transform_dict'] = assemblies
    
    return mol_object

def molecule_local(file_path, 
                   mol_name="Name",
                   include_bonds=True, 
                   center_molecule=False, 
                   del_solvent=True, 
                   default_style=0, 
                   setup_nodes=True
                   ): 
    import biotite.structure as struc
    from .assembly import cif
    
    
    import os
    file_path = os.path.abspath(file_path)
    file_ext = os.path.splitext(file_path)[1]
    
    if file_ext == '.pdb':
        mol, file = open_structure_local_pdb(file_path, include_bonds)
        transforms = assembly.get_transformations_pdb(file)
    elif file_ext == '.pdbx' or file_ext == '.cif':
        mol, file = open_structure_local_pdbx(file_path, include_bonds)
        try:
            transforms = cif.CIFAssemblyParser(file).get_transformations('1')
            transforms = [(sym[0].copy(order='c'), sym[1].copy(order='c'), sym[2].copy(order='c')) for sym in transforms]
            print("got the transforms!")
        except:
            transforms = None
            # self.report({"WARNING"}, message='Unable to parse biological assembly information.')
    else:
        warnings.warn("Unable to open local file. Format not supported.")
    # if include_bonds chosen but no bonds currently exist (mol.bonds is None)
    # then attempt to find bonds by distance
    if include_bonds and not mol.bonds:
        mol.bonds = struc.connect_via_distances(mol[0], inter_residue=True)
    
    if not (file_ext == '.pdb' and file.get_model_count() > 1):
        file = None
        
    
    mol_object, coll_frames = create_molecule(
        mol_array = mol,
        mol_name = mol_name,
        file = file,
        center_molecule = center_molecule,
        del_solvent = del_solvent, 
        include_bonds = include_bonds
        )
    
        
    
    # setup the required initial node tree on the object 
    if setup_nodes:
        nodes.create_starting_node_tree(
            obj = mol_object,
            coll_frames = coll_frames,
            starting_style = default_style
            )
    
    if transforms:
        mol_object['bio_transform_dict'] = transforms
        # mol_object['bio_transnform_dict'] = 'testing'
        
    return mol_object


def open_structure_rcsb(pdb_code, include_bonds = True):
    import biotite.structure.io.mmtf as mmtf
    import biotite.database.rcsb as rcsb
    
    file = mmtf.MMTFFile.read(rcsb.fetch(pdb_code, "mmtf"))
    
    # returns a numpy array stack, where each array in the stack is a model in the 
    # the file. The stack will be of length = 1 if there is only one model in the file
    mol = mmtf.get_structure(file, extra_fields = ["b_factor", "charge"], include_bonds = include_bonds) 
    return mol, file


def open_structure_local_pdb(file_path, include_bonds = True):
    import biotite.structure.io.pdb as pdb
    
    file = pdb.PDBFile.read(file_path)
    
    # returns a numpy array stack, where each array in the stack is a model in the 
    # the file. The stack will be of length = 1 if there is only one model in the file
    mol = pdb.get_structure(file, extra_fields = ['b_factor', 'charge'], include_bonds = include_bonds)
    return mol, file

def open_structure_local_pdbx(file_path, include_bonds = True):
    import biotite.structure as struc
    import biotite.structure.io.pdbx as pdbx
    
    file = pdbx.PDBxFile.read(file_path)
    
    # returns a numpy array stack, where each array in the stack is a model in the 
    # the file. The stack will be of length = 1 if there is only one model in the file
    mol  = pdbx.get_structure(file, extra_fields = ['b_factor', 'charge'])
    # pdbx doesn't include bond information apparently, so manually create
    # them here if requested
    if include_bonds:
        mol[0].bonds = struc.bonds.connect_via_residue_names(mol[0], inter_residue = True)
    return mol, file

def create_object(name, collection, locations, bonds=[]):
    """
    Creates a mesh with the given name in the given collection, from the supplied
    values for the locations of vertices, and if supplied, bonds as edges.
    """
    # create a new mesh
    mol_mesh = bpy.data.meshes.new(name)
    mol_mesh.from_pydata(locations, bonds, faces=[])
    mol_object = bpy.data.objects.new(name, mol_mesh)
    collection.objects.link(mol_object)
    return mol_object

def add_attribute(object, name, data, type = "FLOAT", domain = "POINT", add = True):
    if not add:
        return None
    attribute = object.data.attributes.new(name, type, domain)
    attribute.data.foreach_set('value', data)

def pdb_get_b_factors(file):
    """
    Get a list, which contains a numpy array for each model containing the b-factors.
    """
    b_factors = []
    for model in range(file.get_model_count()):
        atoms = file.get_structure(model = model + 1, extra_fields = ['b_factor'])
        b_factors.append(atoms.b_factor)
    return b_factors

def create_molecule(mol_array, mol_name, center_molecule = False, 
                    file = None,
                    del_solvent = False, include_bonds = False, collection = None):
    import biotite.structure as struc
    
    if np.shape(mol_array)[0] > 1:
        mol_frames = mol_array
    else:
        mol_frames = None
    
    mol_array = mol_array[0]
    
    # remove the solvent from the structure if requested
    if del_solvent:
        mol_array = mol_array[np.invert(struc.filter_solvent(mol_array))]

    world_scale = 0.01
    locations = mol_array.coord * world_scale
    
    centroid = np.array([0, 0, 0])
    if center_molecule:
        centroid = struc.centroid(mol_array) * world_scale
    

    # subtract the centroid from all of the positions to localise the molecule on the world origin
    if center_molecule:
        locations = locations - centroid

    if not collection:
        collection = coll_mn()
    
    if include_bonds and mol_array.bonds:
        bonds = mol_array.bonds.as_array()
        mol_object = create_object(name = mol_name, collection = collection, locations = locations, bonds = bonds[:, [0,1]])
    else:
        mol_object = create_object(name = mol_name, collection = collection, locations = locations)

    # The attributes for the model are initially defined as single-use functions. This allows
    # for a loop that attempts to add each attibute by calling the function. Only during this
    # loop will the call fail if the attribute isn't accessible, and the warning is reported
    # there rather than setting up a try: except: for each individual attribute which makes
    # some really messy code.
    
    # I still don't like this as an implementation, and welcome any cleaner approaches that 
    # anybody might have.
    
    def att_atomic_number():
        atomic_number = np.array(list(map(
            lambda x: data.elements.get(x, {'atomic_number': -1}).get("atomic_number"), 
            np.char.title(mol_array.element))))
        return atomic_number
    
    def att_res_id():
        return mol_array.res_id
    
    def att_res_name():
        other_res = []
        counter = 0
        id_counter = -1
        res_names = mol_array.res_name
        res_names_new = []
        res_ids = mol_array.res_id
        res_nums  = []
        
        for name in res_names:
            res_num = data.residues.get(name, {'res_name_num': 9999}).get('res_name_num')
            
            if res_num == 9999:
                if res_names[counter - 1] != name or res_ids[counter] != res_ids[counter - 1]:
                    id_counter += 1
                
                unique_res_name = str(id_counter + 100) + "_" + str(name)
                other_res.append(unique_res_name)
                
                num = np.where(np.isin(np.unique(other_res), unique_res_name))[0][0] + 100
                res_nums.append(num)
            else:
                res_nums.append(res_num)
            counter += 1

        mol_object['ligands'] = np.unique(other_res)
        return np.array(res_nums)

    
    def att_chain_id():
        chain_id = np.searchsorted(np.unique(mol_array.chain_id), mol_array.chain_id)
        return chain_id
    
    def att_b_factor():
        return mol_array.b_factor
    
    def att_vdw_radii():
        vdw_radii =  np.array(list(map(
            # divide by 100 to convert from picometres to angstroms which is what all of coordinates are in
            lambda x: data.elements.get(x, {'vdw_radii': 100}).get('vdw_radii', 100) / 100,  
            np.char.title(mol_array.element)
            )))
        return vdw_radii * world_scale
    
    def att_atom_name():
        atom_name = np.array(list(map(
            lambda x: data.atom_names.get(x, 9999), 
            mol_array.atom_name
        )))
        
        return atom_name
    
    def att_is_alpha():
        return np.isin(mol_array.atom_name, 'CA')
    
    def att_is_solvent():
        return struc.filter_solvent(mol_array)
    
    def att_is_backbone():
        is_backbone = (struc.filter_backbone(mol_array) | 
                        np.isin(mol_array.atom_name, ["P", "O5'", "C5'", "C4'", "C3'", "O3'"]))
        return is_backbone
    
    def att_is_nucleic():
        return struc.filter_nucleotides(mol_array)
    
    def att_is_peptide():
        aa = struc.filter_amino_acids(mol_array)
        con_aa = struc.filter_canonical_amino_acids(mol_array)
        
        return aa | con_aa
    
    def att_is_hetero():
        return mol_array.hetero
    
    def att_is_carb():
        return struc.filter_carbohydrates(mol_array)
    

    # Add information about the bond types to the model on the edge domain
    # Bond types: 'ANY' = 0, 'SINGLE' = 1, 'DOUBLE' = 2, 'TRIPLE' = 3, 'QUADRUPLE' = 4
    # 'AROMATIC_SINGLE' = 5, 'AROMATIC_DOUBLE' = 6, 'AROMATIC_TRIPLE' = 7
    # https://www.biotite-python.org/apidoc/biotite.structure.BondType.html#biotite.structure.BondType
    if include_bonds:
        try:
            add_attribute(
                object = mol_object, 
                name = 'bond_type', 
                data = bonds[:, 2].copy(order = 'C'), # the .copy(order = 'C') is to fix a weird ordering issue with the resulting array
                type = "INT", 
                domain = "EDGE"
                )
        except:
            warnings.warn('Unable to add bond types to the molecule.')

    
    # these are all of the attributes that will be added to the structure
    # TODO add capcity for selection of particular attributes to include / not include to potentially
    # boost performance, unsure if actually a good idea of not. Need to do some testing.
    attributes = (
        {'name': 'res_id',          'value': att_res_id,              'type': 'INT',     'domain': 'POINT'},
        {'name': 'res_name',        'value': att_res_name,            'type': 'INT',     'domain': 'POINT'},
        {'name': 'atomic_number',   'value': att_atomic_number,       'type': 'INT',     'domain': 'POINT'},
        {'name': 'b_factor',        'value': att_b_factor,            'type': 'FLOAT',   'domain': 'POINT'},
        {'name': 'vdw_radii',       'value': att_vdw_radii,           'type': 'FLOAT',   'domain': 'POINT'},
        {'name': 'chain_id',        'value': att_chain_id,            'type': 'INT',     'domain': 'POINT'},
        {'name': 'atom_name',       'value': att_atom_name,           'type': 'INT',     'domain': 'POINT'},
        {'name': 'is_backbone',     'value': att_is_backbone,         'type': 'BOOLEAN', 'domain': 'POINT'},
        {'name': 'is_alpha_carbon', 'value': att_is_alpha,            'type': 'BOOLEAN', 'domain': 'POINT'},
        {'name': 'is_solvent',      'value': att_is_solvent,          'type': 'BOOLEAN', 'domain': 'POINT'},
        {'name': 'is_nucleic',      'value': att_is_nucleic,          'type': 'BOOLEAN', 'domain': 'POINT'},
        {'name': 'is_peptide',      'value': att_is_peptide,          'type': 'BOOLEAN', 'domain': 'POINT'},
        {'name': 'is_hetero',       'value': att_is_hetero,           'type': 'BOOLEAN', 'domain': 'POINT'},
        {'name': 'is_carb',         'value': att_is_carb,             'type': 'BOOLEAN', 'domain': 'POINT'}
    )
    
    # assign the attributes to the object
    for att in attributes:
        # try:
        add_attribute(mol_object, att['name'], att['value'](), att['type'], att['domain'])
        # except:
            # warnings.warn(f"Unable to add attribute: {att['name']}")

    if mol_frames:
        try:
            b_factors = pdb_get_b_factors(file)
        except:
            b_factors = None
        # create the frames of the trajectory in their own collection to be disabled
        coll_frames = bpy.data.collections.new(mol_object.name + "_frames")
        collection.children.link(coll_frames)
        counter = 0
        for frame in mol_frames:
            obj_frame = create_object(
                name = mol_object.name + '_frame_' + str(counter), 
                collection=coll_frames, 
                locations= frame.coord * world_scale - centroid
            )
            if b_factors:
                try:
                    add_attribute(obj_frame, 'b_factor', b_factors[counter])
                except:
                    b_factors = False
            counter += 1
        
        # disable the frames collection so it is not seen
        bpy.context.view_layer.layer_collection.children[collection.name].children[coll_frames.name].exclude = True
    else:
        coll_frames = None
    
    # add custom properties to the actual blender object, such as number of chains, biological assemblies etc
    # currently biological assemblies can be problematic to holding off on doing that
    try:
        mol_object['chain_id_unique'] = list(np.unique(mol_array.chain_id))
    except:
        warnings.warn('No chain information detected.')
    
    return mol_object, coll_frames
