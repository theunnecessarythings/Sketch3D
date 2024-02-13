bl_info = {
    "name": "Sketch3D",
    "author": "Sreeraj R",
    "version": (1, 0),
    "blender": (2, 83, 0),
    "location": "View3D > Edit Mode > Toolbar",
    "description": "Draw mesh in Edit Mode",
    "warning": "Made purely for fun, don't expect stuff to work ;)",
    "doc_url": "",
    "category": "Add Mesh",
}
    
import bpy
from bpy_extras.view3d_utils import region_2d_to_location_3d, region_2d_to_vector_3d, region_2d_to_origin_3d

import mathutils
from mathutils import Vector
import bmesh
from math import sin, cos, pi, degrees
import time
import sys
from bpy.utils.toolsystem import ToolDef
toolSketch3D = "3D View Tool: Edit, Sketch3D"



class ModalDrawOperator(bpy.types.Operator):
    """Draw 3D mesh"""
    bl_idname = "view3d.sketch_3d"
    bl_label = "Sketch3D"
    bl_options = {"REGISTER", "UNDO"}
    
    placement_items = [
        ("VIEW", "View", "", "RESTRICT_VIEW_ON", 1),
        ("SURFACE", "Surface", "", "FACESEL", 2),
        ("CURSOR", "3D Cursor", "", "PIVOT_CURSOR", 3),
    ]
    
    radius: bpy.props.FloatProperty(name='Radius', default=0.1, min=0)
    strength: bpy.props.FloatProperty(name='Strength', default=1, min=0, max=1)
    segments: bpy.props.IntProperty(name='Segments', default=8, min=2, max=128)
    min_distance: bpy.props.FloatProperty(name='Min Distance', default=0.01, min=0)
    pen_pressure: bpy.props.BoolProperty(name='Pen Pressure', default=True)
    placement: bpy.props.EnumProperty(name='Placement', default='VIEW', items=placement_items)
    offset: bpy.props.BoolProperty(name='Offset', default=False)
    
                
    def create_circle(self, segments, radius, matrix):
        edges = []
        verts = []
        for i in range(segments):
            x = radius * sin(2*pi/segments*i)
            y = radius * cos(2*pi/segments*i)
            vec = matrix @ Vector((x,y,0))
            verts.append(self.bm.verts.new(vec))
        
        for i in range(segments-1):
            edges.append(self.bm.edges.new((verts[i], verts[i+1])))
        edges.append(self.bm.edges.new((verts[0], verts[segments-1])))
        return verts, edges
            
    def add_vertex(self, loc, pressure, surface, normal):
        self.count += 1
        if self.count == 2 :
            #fix first point orientation
            dir = Vector(self.prev) - Vector(loc)
            up = Vector((0,0,-1))
            quat = up.rotation_difference(dir)
            
            mat_loc = mathutils.Matrix.Translation(self.prev)
            mat_loc_i = mat_loc.inverted()
            for vert in self.prev_verts:
                vert.co = mat_loc_i @ vert.co
                vert.co = mat_loc @ quat.to_matrix().to_4x4() @ vert.co
            
        if not self.pen_pressure:
            pressure = 1
        radius = self.radius * self.strength * pressure
        if surface and self.offset:
            loc = loc + radius * normal
            
        mat_loc = mathutils.Matrix.Translation(loc)
        #check min distance
        if self.atleast_one:
            dir = Vector(loc) - Vector(self.prev)
            if dir.length < self.min_distance:
                return
        if self.atleast_one:
            #calc orientation
            dir = Vector(loc) - Vector(self.prev)
            up = Vector((0,0,1))
            quat = up.rotation_difference(dir)
            mat_loc = mat_loc @ quat.to_matrix().to_4x4()

            
        verts, self.circle = self.create_circle(self.segments, radius, mat_loc)
        
        self.prev = loc
        if self.atleast_one:
            edges = self.circle + self.prev_edges
            bmesh.ops.bridge_loops(self.bm, edges=edges)
            
        self.prev_edges = self.circle
        self.prev_verts = verts
        self.atleast_one = True
        bmesh.update_edit_mesh(self.me)


    def interpolate_stroke(self):
        pass

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            loc = (event.mouse_region_x, event.mouse_region_y)
            region = context.region
            rv3d = context.space_data.region_3d
            vec = region_2d_to_vector_3d(region, rv3d, loc)   
            
            viewlayer = context.view_layer
            then = time.time()
            view_vector = region_2d_to_vector_3d(region, rv3d, loc)
            ray_origin = region_2d_to_origin_3d(region, rv3d, loc)
            result = None
            normal = None
            if self.placement == 'SURFACE':
                result, location, normal, index, object, matrix = context.scene.ray_cast(viewlayer, ray_origin, view_vector)
            elif self.placement == 'CURSOR':
                vec = context.scene.cursor.location
            if not result:
                location = region_2d_to_location_3d(region, rv3d, loc, vec)
                
            #fix location
            location = context.object.matrix_world.inverted() @ location
            self.add_vertex(location, event.pressure, self.placement=='SURFACE', normal)
            


        elif event.type == 'LEFTMOUSE':
            if self.placement == 'SURFACE':
                self.interpolate_stroke()
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.area.type == 'VIEW_3D':
            self.mouse_path = []

            context.window_manager.modal_handler_add(self)
            bpy.ops.mesh.select_all(action='DESELECT')
            self.obj = context.object
            self.me = self.obj.data
            self.bm = bmesh.from_edit_mesh(self.me)
            self.bm.select_mode = {'VERT', 'EDGE'}
            self.atleast_one = False
            self.count = 0
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}


@ToolDef.from_fn
def toolSketch3DDraw():
    
    def draw_settings(context, layout, tool):
        props = tool.operator_properties('view3d.sketch_3d')
        layout.prop(props, 'radius')
        row = layout.row(align=True)
        row.prop(props, 'strength', slider=True)
        row.prop(props, 'pen_pressure', icon_only=True, icon='STYLUS_PRESSURE')
        layout.prop(props, 'segments')
        layout.prop(props, 'min_distance')
        layout.prop(props, 'placement')
        if props.placement == 'SURFACE':
            layout.prop(props, 'offset')
    
    return dict(idname = "sketch_3d.draw_tool",
        label = "Sketch3D",
        description = "Draw 3D mesh in Edit Mode",
        icon = "brush.paint_vertex.draw",
        widget = None,
        keymap = toolSketch3D,
        draw_settings = draw_settings,
        )

def getToolList(spaceType, contextMode):
    from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
    cls = ToolSelectPanelHelper._tool_class_from_space_type(spaceType)
    return cls._tools[contextMode]

def registerSketch3D():
    tools = getToolList('VIEW_3D', 'EDIT_MESH')
    tools += None, toolSketch3DDraw
    # ~ tools += None, toolFlexiEdit
    del tools


def unregisterSketch3D():
    tools = getToolList('VIEW_3D', 'EDIT_MESH')

    index = tools.index(toolSketch3DDraw) - 1 #None
    tools.pop(index)
    tools.remove(toolSketch3DDraw)
    del tools


keymapDraw = (toolSketch3D,
        {"space_type": 'VIEW_3D', "region_type": 'WINDOW'},
        {"items": [
            ("view3d.sketch_3d", {"type": 'LEFTMOUSE', "value": 'PRESS'},
             {"properties": []}),
        ]},)

emptyKeymapDraw = (toolSketch3D,
        {"space_type": 'VIEW_3D', "region_type": 'WINDOW'},
        {"items": []},)


def registerSketch3DKeymaps():
    keyconfigs = bpy.context.window_manager.keyconfigs
    kc_defaultconf = keyconfigs.default
    kc_addonconf = keyconfigs.addon

    from bl_keymap_utils.io import keyconfig_init_from_data
    keyconfig_init_from_data(kc_defaultconf, [emptyKeymapDraw])

    keyconfig_init_from_data(kc_addonconf, [keymapDraw])

def unregisterSketch3DKeymaps():
    keyconfigs = bpy.context.window_manager.keyconfigs
    defaultmap = keyconfigs.get("blender").keymaps
    addonmap   = keyconfigs.get("blender addon").keymaps

    for km_name, km_args, km_content in [keymapDraw]:
        keymap = addonmap.find(km_name, **km_args)
        keymap_items = keymap.keymap_items
        for item in km_content['items']:
            item_id = keymap_items.find(item[0])
            if item_id != -1:
                keymap_items.remove(keymap_items[item_id])
        addonmap.remove(keymap)
        defaultmap.remove(defaultmap.find(km_name, **km_args))

classes = [
    ModalDrawOperator
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    registerSketch3D()
    registerSketch3DKeymaps()

def unregister():

    unregisterSketch3DKeymaps()
    unregisterSketch3D()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
    

