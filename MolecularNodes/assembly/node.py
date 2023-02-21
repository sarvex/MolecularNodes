import bpy
from .. import nodes

def create_assembly_node(name, assembly):
    
    node_mat = bpy.data.node_groups.get('MOL_RotTransMat_' + name)
    if node_mat:
        return node_mat
    
    node_mat = nodes.gn_new_group_empty('MOL_RotTransMat_' + name)
    node_mat.inputs.remove(node_mat.inputs['Geometry'])
    node_mat.nodes['Group Output'].location = [800, 0]
    node_mat.outputs['Geometry'].name = 'RotTransMat'
    
    node_transform_list = []
    for i, sym in enumerate(assembly):
        node = nodes.rotation_matrix_sym(
            node_group=node_mat, 
            sym=sym, 
            location=[0, 0 - (300 * i)]
        )
        node_transform_list.append(node)
    
    node_transform_list.reverse()
    
    node_join = node_mat.nodes.new('GeometryNodeJoinGeometry')
    node_join.location = [300, 0]
    
    for node_transform in node_transform_list:
        node_mat.links.new(node_transform.outputs['Geometry'], node_join.inputs['Geometry'])
    
    node_mat.links.new(node_join.outputs['Geometry'], node_mat.nodes['Group Output'].inputs['RotTransMat'])
    
    return node_mat

def create_biological_assembly_node(name, assembly):
    
    node_bio = bpy.data.node_groups.get('MOL_assembly_' + name)
    if node_bio:
        return node_bio
    
    # try to create the assembly transformation nodes first, so 
    # if they fail, nothing else is created
    data_trans = create_assembly_node(name, assembly)
    
    node_bio = nodes.gn_new_group_empty('MOL_assembly_' + name)
    
    node_input = node_bio.nodes[bpy.app.translations.pgettext_data("Group Input",)]
    node_output = node_bio.nodes[bpy.app.translations.pgettext_data("Group Output",)]
    
    
    node_output.location = [400, 0]
    node_output.inputs['Geometry'].name = 'Instances'
    
    node_assembly = nodes.add_custom_node_group_to_node(node_bio, 'MOL_utils_bio_assembly', location=[0, 0])
    
    node_trans = nodes.add_custom_node_group_to_node(node_bio, data_trans.name, location = [-400, -200])
    
    link = node_bio.links.new
    
    link(node_input.outputs['Geometry'], node_assembly.inputs['Geometry'])
    link(node_trans.outputs['RotTransMat'], node_assembly.inputs['RotTransMat'])
    link(node_assembly.outputs['Instances'], node_output.inputs['Instances'])
    
    inputs = (
        {'name': 'Scale Rotation', 
         'type': 'NodeSocketFloat', 
         'default': 1},
        {'name': 'Scale Translation', 
         'type': 'NodeSocketFloat', 
         'default': 1}
    )
    
    for input in inputs:
        name = input.get('name')
        type = input.get('type')
        default = input.get('default')
        
        node_bio.inputs.new(type, name)
        node_bio.inputs.get(name).default_value = default
        
        link(node_input.outputs[name], node_assembly.inputs[name])
    
    return node_bio
