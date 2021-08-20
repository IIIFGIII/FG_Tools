bl_info = {
	"name": "ARR",
	"author": "IIIFGIII (discord IIIFGIII#7758)",
	"version": (1, 1),
	"blender": (2, 83, 0),
	"location": "Viev3D > N panel > FGT > ARR",
	"description": "Addon remove + reinstall by filepath",
	"warning": "",
	"wiki_url": "https://github.com/IIIFGIII/FG_Tools",
	"category": "FG_Tools",
}

import bpy,os

class ARR_PT_Panel(bpy.types.Panel):
	bl_label = 'ARR'
	bl_idname = 'ARR_PT_Panel'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		arr = context.scene.arr_props
		layout = self.layout
		col = layout.column(align=True)
		col.prop(arr, 'arr_path', text= '')
		col.operator('fgt.arr_remove_reinstall', icon= 'FILE_REFRESH', text= 'Remove + Reinstall')


class ARR_OT_Remove_Reinstall(bpy.types.Operator):
	bl_idname = 'fgt.arr_remove_reinstall'
	bl_label = 'ARR_OT_Remove_Reinstall'
	bl_options = {'REGISTER'}

	def execute(self,context):
		arr = context.scene.arr_props
		pre = bpy.ops.preferences
		if not os.path.exists(bpy.path.abspath(arr.arr_path)):
			self.report({'ERROR'}, f' File path "{arr.arr_path}" not exist!!!')
			return{'FINISHED'}	
		pre.addon_install(overwrite=True, filepath= bpy.path.abspath(arr.arr_path))
		pre.addon_enable(module= bpy.path.display_name_from_filepath(arr.arr_path))
		return {'FINISHED'}

class ARR_Settings_Props(bpy.types.PropertyGroup): 
	arr_path: bpy.props.StringProperty(
		default='', 
		subtype='FILE_PATH')

CTR = [ARR_PT_Panel,ARR_OT_Remove_Reinstall,ARR_Settings_Props]

def register():
	for cls in CTR:
		bpy.utils.register_class(cls)
	# Register properties		
	bpy.types.Scene.arr_props = bpy.props.PointerProperty(type=ARR_Settings_Props)

def unregister():
	for cls in reversed(CTR):
		bpy.utils.unregister_class(cls)
	# Delete properties
	del bpy.types.Scene.arr_props
