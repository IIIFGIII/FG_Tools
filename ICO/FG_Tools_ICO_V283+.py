bl_info = {
	"name": "ICO",
	"author": "IIIFGIII (discord IIIFGIII#7758)",
	"version": (1, 1),
	"blender": (2, 83, 0),
	"location": "Viev3D > N panel > FGT > ICO",
	"description": "Preview of existing icons/icons names.",
	"warning": "",
	"wiki_url": "https://github.com/IIIFGIII/FG_Tools/wiki/ICO",
	"category": "FG_Tools",
}

import bpy

bpr = bpy.props

class ICO_PT_Panel(bpy.types.Panel):
	bl_label = 'ICO'
	bl_idname = 'ICO_PT_Panel'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_options = {'DEFAULT_CLOSED'}


	def draw(self,context):
		layout = self.layout
		col = layout.column(align=True)

		props = context.scene.ico_props
		ico_s = props.ico_sorting
		ico_f = props.ico_filter
		
		col.prop(props, 'ico_sorting', text= '' )
		if ico_s == 'm1':
			icons = bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys()
		else:
			icons = sorted(bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items.keys())

		col.prop(props, 'ico_filter', text = '' )
		for ico in icons:
			if ico_f == '':
				col.operator('fgt.ico_check', icon= ico, text= ico).copy = ico
			elif ico.find(ico_f.upper()) != -1:
				col.operator('fgt.ico_check', icon= ico, text= ico).copy = ico

class ICO_OP_Operator(bpy.types.Operator):
	bl_idname = 'fgt.ico_check'
	bl_label = 'ICO_OP_Operator'
	bl_option = {'REGISTER'}
	bl_description = 'Press button to copy name to clipboard'

	copy: bpr.StringProperty(name= '', default= '')

	def execute(self, context):
		bpy.context.window_manager.clipboard = self.copy
		self.report({'INFO'}, f'{self.copy} copied to clipboard.')
		return{'FINISHED'}

class ICO_Settings_Props(bpy.types.PropertyGroup):

	ico_sorting: bpr.EnumProperty(
		name='Sorting method',
		description = 'Des',
		items=[('m1','Blender','',1), ('m2','Alphabetical','',2)],
	)

	ico_filter: bpr.StringProperty(
		name = 'Filter icon name.',
		default = '',
	)


CTR = [
	ICO_PT_Panel,
	ICO_OP_Operator,
	ICO_Settings_Props,
	]

def register():
	for cls in CTR:
		bpy.utils.register_class(cls)
	bpy.types.Scene.ico_props = bpy.props.PointerProperty(type=ICO_Settings_Props)

def unregister():
	for cls in CTR:
		bpy.utils.unregister_class(cls)
	del bpy.types.Scene.ico_props
