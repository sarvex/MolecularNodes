import bpy
import numpy as np
import warnings
from .. import nodes

def create_biological_assembly_node(name, assemblies_list, unique_chain_ids, by_chain = False):
    
    node_bio = bpy.data.node_groups.get('MOL_assembly_' + name)
    if node_bio:
        return node_bio
    
    node_bio = nodes.gn_new_group_empty('MOL_assembly_' + name)
    
    node_input = node_bio.nodes[bpy.app.translations.pgettext_data("Group Input",)]
    node_output = node_bio.nodes[bpy.app.translations.pgettext_data("Group Output",)]
    
    assembly_nodes_list = []
    for i, assembly in enumerate(assemblies_list):
        # try to create the assembly transformation nodes first, so 
        # if they fail, nothing else is created
        data_trans = create_assembly_node(
            name = f"MOL_data_{name}_assembly_{i}", 
            assembly = assembly, 
            unique_chain_ids = unique_chain_ids, 
            assembly_id=i, 
            by_chain = by_chain
            )    
        assembly_nodes_list.append(data_trans)
    
    node_output.location = [400, 0]
    node_output.inputs['Geometry'].name = 'Instances'
    
    node_assembly = nodes.add_custom_node_group_to_node(
        node_bio, 
        'MOL_utils_bio_assembly', 
        location=[0, 0]
        )
    
    node_trans_list = []
    for i, node in enumerate(assembly_nodes_list):
        node_trans = nodes.add_custom_node_group_to_node(
            node_bio, 
            node.name, 
            location = [-400, int(-400 * (i + 1))]
            )
        node_trans_list.append(node_trans)
    
    link = node_bio.links.new
    
    node_joined_transforms = nodes.nodes_to_geometry(node_bio, node_trans_list, output = 0)
    node_joined_transforms.location = [-200, -400]
    
    link(node_input.outputs['Geometry'], node_assembly.inputs['Geometry'])
    link(node_joined_transforms.outputs[0], node_assembly.inputs['RotTransMat'])
    link(node_assembly.outputs['Instances'], node_output.inputs['Instances'])
    
    inputs = (
        {
            'name': 'Scale Rotation', 
            'type': 'NodeSocketFloat', 
            'default': 1
        },
        {
            'name': 'Scale Translation', 
            'type': 'NodeSocketFloat', 
            'default': 1
        }, 
        {
            'name': 'Assembly ID', 
            'type': 'NodeSocketInt', 
            'default': 0
        }, 
        {
            'name': 'By Chain', 
            'type': 'NodeSocketBool', 
            'default': False
        }
    )
    
    for input in inputs:
        try:
            name = input.get('name')
            type = input.get('type')
            default = input.get('default')

            node_bio.inputs.new(type, name)
            node_bio.inputs.get(name).default_value = default
            link(node_input.outputs[name], node_assembly.inputs[name])
        except:
            warnings.warn(
                f"Unable to setup node input {name} while setting up {node_bio.name}."
            )
        
    
    node_bio.inputs['Assembly ID'].min_value = 0
    node_bio.inputs['Assembly ID'].max_value = i
    
    return node_bio

def create_assembly_node(name, assembly, unique_chain_ids, assembly_id, by_chain = False):
    
    node_mat = bpy.data.node_groups.get(name)
    if node_mat:
        return node_mat
    
    node_mat = nodes.gn_new_group_empty(name)
    node_mat.inputs.remove(node_mat.inputs['Geometry'])
    node_mat.nodes['Group Output'].location = [800, 0]
    node_mat.outputs['Geometry'].name = 'RotTransMat'
    
    node_transform_list = []
    for i, sym in enumerate(assembly):
        if by_chain:
            for chain in sym[0]:
                chain_num = np.where(np.isin(unique_chain_ids, chain))[0][0]
                node = rotation_matrix_sym(
                    node_group=node_mat, 
                    sym=sym, 
                    symmetry_id=i,
                    assembly_id=assembly_id,
                    chain=chain_num,
                    location=[0, 0 - (300 * i)]
                )
                node_transform_list.append(node)
        else:
            node = rotation_matrix_sym(
                node_group = node_mat, 
                sym = sym, 
                symmetry_id=i,
                assembly_id=assembly_id,
                chain=0,
                location=[0, 0 - (300 * i)]
            )
            node_transform_list.append(node)
    
    node_transform_list.reverse()
    
    node_join = node_mat.nodes.new('GeometryNodeJoinGeometry')
    node_join.location = [300, 0]
    
    for node_transform in node_transform_list:
        node_mat.links.new(
            node_transform.outputs['Geometry'], 
            node_join.inputs['Geometry']
            )
    
    node_mat.links.new(
        node_join.outputs['Geometry'], 
        node_mat.nodes['Group Output'].inputs['RotTransMat']
        )
    
    return node_mat

def rotation_matrix_sym(node_group, sym, symmetry_id, assembly_id, chain,
                        location = [0,0], 
                        world_scale = 0.01) :
    """Add a Rotation & Translation node from a 3x4 matrix.

    Args:
        node_group (_type_): Parent node group to add this new node to.
        mat (_type_): 3x4 rotation & translation matrix
        location (list, optional): Position to add the node in the node tree. Defaults 
        to [0,0].
        world_scale(float, optional): Scaling factor for the world. Defaults to 0.01.
    Returns:
        _type_: Newly created node tree.
    """
    from scipy.spatial.transform import Rotation as R
    
    node_utils_rot = nodes.mol_append_node('MOL_utils_rot_trans')
    
    node = node_group.nodes.new('GeometryNodeGroup')
    node.node_tree = node_utils_rot
    node.location = location
    
    rot_mat = np.array(sym[1]).reshape(3,3)
    
    # calculate the euler rotation from the rotation matrix
    rotation = R.from_matrix(rot_mat).as_euler('xyz')
    
    # set the values for the node that was just created
    # set the euler rotation values
    for i in range(3):
        node.inputs[0].default_value[i] = rotation[i]
    # set the translation values
    for i in range(3):
        node.inputs[1].default_value[i] = sym[2][i] * world_scale
    
    node.inputs['chain'].default_value = chain
    node.inputs['symmetry'].default_value = symmetry_id
    node.inputs['assembly'].default_value = assembly_id
    
    return node




# def bio_assemblies_node(assemblies_list):
#     node_list = []
    
#     for assembly, i in enumerate(assemblies_list):
#         node_list.append(node_single_assembly(assembly, i))

#     node_bio_assemblies = join_nodes(this_node, node_list)
    
#     return node_bio_assemblies