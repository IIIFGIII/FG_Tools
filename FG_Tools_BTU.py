bl_info = {
	"name": "BTU",
	"author": "FG_Tools",
	"version": (1, 0),
	"blender": (2, 80, 0),
	"location": "Viev3D > N panel > BTU",
	"description": "Simple tools for transfering objects to Unreal Engine",
	"warning": "",
	"wiki_url": "",
	"category": "FG_Tools",
}

import bpy,os,io,math

# Panel layout -----------------------------------------------------------------


class BTU_PT_Panel(bpy.types.Panel):
	bl_label = 'Blender To Unreal'
	bl_idname = 'BTU_PT_Panel'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FG_Tools'
	bl_context = 'objectmode'


	def draw(self,context):
		pass


class BTU_PT_Tools(bpy.types.Panel):
	bl_label = 'BTU Tools'
	bl_idname = 'BTU_PT_Tools'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_parent_id = 'BTU_PT_Panel'

	def draw(self,context):
		layout = self.layout
		col = layout.column(align=True)
#		box = col.box()
#		col = box.column(align=True)

		col.prop(context.scene.btu_props, 'btu_exp_path', text= '')
		col.operator('fg.btu_exp_op', icon='EXPORT', text='Export FBX')
		col.operator('fg.btu_copy_obj', icon='COPYDOWN', text='Copy To UE')

class BTU_PT_Settings(bpy.types.Panel):
	bl_label = 'BTU Settings'
	bl_idname = 'BTU_PT_Settings'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_options = {'DEFAULT_CLOSED'}
	bl_parent_id = 'BTU_PT_Panel'

	def draw(self,context):
		layout = self.layout
		col = layout.column(align=True)
#		box = col.box()
#		col = box.column(align=True)

		col.label(text="Expor Settings")
		col.prop(context.scene.btu_props, 'btu_exp_scale', text= 'Export Scale')
		col.prop(context.scene.btu_props, 'btu_exp_apptra', text= 'Apply Object Transforms?')

		if context.scene.btu_props.btu_exp_apptra:
			col.prop(context.scene.btu_props, 'btu_exp_apploc', text= 'Apply Location')
			col.prop(context.scene.btu_props, 'btu_exp_approt', text= 'Apply Rotation')
			col.prop(context.scene.btu_props, 'btu_exp_appscl', text= 'Apply Scale')

		col.label(text="Copy Settings")
		col.prop(context.scene.btu_props, 'btu_copy_underline', text= 'Replace "." by "_"')



# Exporter -------------------------------------------------------------

class BTU_Expop(bpy.types.Operator):
	bl_idname = 'fg.btu_exp_op'
	bl_label = 'EXPORT_Operator'
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = 'Export individual .fbx for each object in selection (filter mesh objects only!!!).'

	def execute(self, context):

		selected_obj_names=[]
		exp_scale = context.scene.btu_props.btu_exp_scale
		selected_obj = bpy.context.selected_objects
	
		for obj in selected_obj:
			if obj.type == 'MESH':
				selected_obj_names.append(obj.name)
	
		if not selected_obj_names:
			self.report({'ERROR'}, f' No mesh objects in selection!')
			return{'FINISHED'}
		#Reject execute -------------------------------------------------------

		# Check custom path -> rollback to default if wrong
		if context.scene.btu_props.btu_exp_path != '//Export/':
			exp_folder = bpy.path.abspath(context.scene.btu_props.btu_exp_path)
			if not os.path.exists(exp_folder):
				self.report({'ERROR'}, f' Your custom path not exist! Trying default "//Export/" path.')		
				context.scene.btu_exp_path = '//Export/'
		
		# Check default path
		if context.scene.btu_props.btu_exp_path == '//Export/':
			if (bpy.path.abspath('//') != ''):
				exp_folder = bpy.path.abspath(context.scene.btu_props.btu_exp_path)
				if not os.path.exists(exp_folder):
					os.makedirs(exp_folder)
			else:
				self.report({'ERROR'}, f' Save .blend file somewhere or choose folder for export.')
				return{'FINISHED'}
		#Reject execute --------------------------------------------------------

		# Exporter loop body

		ob_act = bpy.context.view_layer.objects.active
		bpy.ops.object.select_all(action='DESELECT')
		obj_num = 0 

		for name in selected_obj_names:

			comb_exp_path = exp_folder + name + '.fbx'
			bpy.data.objects[name].select_set(True)
			obj_num += 1

			bpy.ops.object.duplicate()

			if context.scene.btu_props.btu_exp_apploc:
				bpy.ops.apply.transformlocrotscale(option='LOC')
			if context.scene.btu_props.btu_exp_approt:
				bpy.ops.apply.transformlocrotscale(option='ROT')
			if context.scene.btu_props.btu_exp_appscl:
				bpy.ops.apply.transformlocrotscale(option='SCALE')

			bpy.ops.export_scene.fbx(

				filepath=comb_exp_path,

				use_selection=True, 
				object_types={'MESH'},

				apply_unit_scale=True,
				bake_space_transform=True,
				axis_forward='Y',
				axis_up='Z',
				global_scale=exp_scale,

				bake_anim=False

				)

			bpy.ops.object.delete()
			bpy.ops.object.select_all(action='DESELECT')


		# Recover selection, filter mesh objects only	
		for name in selected_obj_names:
			bpy.data.objects[name].select_set(True)

		bpy.context.view_layer.objects.active = ob_act

		self.report({'INFO'}, f'Exported {obj_num} objects to {exp_folder}')
		return{'FINISHED'}

class BTU_Copy_Objects(bpy.types.Operator):
	bl_idname = 'fg.btu_copy_obj'
	bl_label = 'COPY_Operator'
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = 'Copy selected objects data to clipboard for pasting in to UE.'

	def execute(self, context):

		if len(bpy.context.selected_objects) != 0:


			bpy.context.window_manager.clipboard = ''
			out_ob_data = io.StringIO()

			out_ob_data.write("Begin Map\n\tBegin Level\n\n")

			obj_num = 0

			for sob in bpy.context.selected_objects:

				obj_num += 1

				sob_n = sob.name
				if context.scene.btu_props.btu_copy_underline:
					sob_n = sob_n.replace('.','_')
				
				out_ob_data.write("\t\tBegin Actor Class=/Script/Engine.StaticMeshActor\n")
				out_ob_data.write("\t\t\tBegin Object Class=/Script/Engine.StaticMeshComponent Name=\"StaticMeshComponent0\" Archetype=StaticMeshComponent'/Script/Engine.Default__StaticMeshActor:StaticMeshComponent0'\n")
				out_ob_data.write("\t\t\tEnd Object\n")
				out_ob_data.write("\t\t\t\tBegin Object Name=\"StaticMeshComponent0\"\n")
				out_ob_data.write("\t\t\t\t\tStaticMesh=StaticMesh'/Engine/EditorMeshes/EditorCube.EditorCube'\n")
				out_ob_data.write(("\t\t\t\t\tRelativeLocation=(X=%f,Y=%f,Z=%f)\n") % (sob.location[0] * 100, ((sob.location[1] * 100) * -1), sob.location[2] * 100))
				out_ob_data.write(("\t\t\t\t\tRelativeRotation=(Pitch=%.5f,Yaw=%.5f,Roll=%.5f)\n") % (math.degrees(sob.rotation_euler.y) * -1, math.degrees(sob.rotation_euler.z) * -1, math.degrees(sob.rotation_euler.x)))
				out_ob_data.write(("\t\t\t\t\tRelativeScale3D=(X=%f,Y=%f,Z=%f)\n") % (sob.scale[0], sob.scale[1], sob.scale[2]))
				out_ob_data.write("\t\t\t\tEnd Object\n\n")
				out_ob_data.write("\t\t\tStaticMeshComponent=\"StaticMeshComponent0\"\n")
				out_ob_data.write("\t\t\tRootComponent=\"StaticMeshComponent0\"\n")
				out_ob_data.write("\t\t\tActorLabel=\"%s\"\n" % str(sob_n))
				out_ob_data.write("\t\tEnd Actor\n\n")

			out_ob_data.write("\n\tEnd Level\nEnd Map\n\n")
			bpy.context.window_manager.clipboard = out_ob_data.getvalue()

			out_ob_data.close()

			self.report({'INFO'}, f'Copied to clipboard {obj_num} objects.')
			return{'FINISHED'}	

		self.report({'ERROR'}, f' No objects selected ... ')
		return{'FINISHED'}

#Addon Properties -----------------------------------------------------------------------

class BTU_Settings_Props(bpy.types.PropertyGroup):
	btu_exp_path: bpy.props.StringProperty(
		name='Export folder path. // expression is relative to file location(not work if file not saved)', 
		default='//Export/', 
		subtype='DIR_PATH')
	btu_exp_scale: bpy.props.FloatProperty(
		description='Will export models in this scale.', 
		default=1.0, 
		min=0.001, 
		max=1000.0, 
		step=0.01)

	btu_exp_apptra: bpy.props.BoolProperty(
		name='',
		description="Apply objects transforms.",
		default=False)
	btu_exp_apploc: bpy.props.BoolProperty(
		name='',
		description="Apply objects lacations - bpy.ops.apply.transformlocrotscale(option='LOC')",
		default=False)
	btu_exp_approt: bpy.props.BoolProperty(
		name='',
		description="Apply objects rotations - bpy.ops.apply.transformlocrotscale(option='ROT')",
		default=False)
	btu_exp_appscl: bpy.props.BoolProperty(
		name='',
		description="Apply objects scales - bpy.ops.apply.transformlocrotscale(option='SCALE')",
		default=False)
	btu_copy_underline: bpy.props.BoolProperty(
		name='',
		description='Replace " . " (dots) by " _ " (underlines) in object names copied for ue UE.',
		default=True)

#Register/Unregister  ---------------------------------------------------------------

CTR = [
	BTU_PT_Panel,
	BTU_PT_Tools,
	BTU_PT_Settings,
	BTU_Expop,
	BTU_Copy_Objects,
	BTU_Settings_Props,

]

def register():
	for cls in CTR:
		bpy.utils.register_class(cls)
	# Register properties ---------------------------------------------------------
	bpy.types.Scene.btu_props = bpy.props.PointerProperty(type=BTU_Settings_Props)

def unregister():
	for cls in CTR:
		bpy.utils.unregister_class(cls)

	# Delete properties ---------------------------------------------------------
	del bpy.types.Scene.btu_props

#FBX exporter variables ----------------------------------------------------------

#	bpy.ops.export_scene.fbx(
#		filepath="", 
#		check_existing=True, 
#		filter_glob="*.fbx", 
#		use_selection=False, 
#		use_active_collection=False, 
#		global_scale=1, 
#		apply_unit_scale=True, 
#		apply_scale_options='FBX_SCALE_NONE', 
#		bake_space_transform=False, 
#		object_types={'EMPTY', 'CAMERA', 'LIGHT', 'ARMATURE', 'MESH', 'OTHER'}, 
#		use_mesh_modifiers=True, 
#		use_mesh_modifiers_render=True, 
#		mesh_smooth_type='OFF', 
#		use_subsurf=False, use_mesh_edges=False, 
#		use_tspace=False, use_custom_props=False, 
#		add_leaf_bones=True, primary_bone_axis='Y', 
#		secondary_bone_axis='X', 
#		use_armature_deform_only=False, 
#		armature_nodetype='NULL', 
#		bake_anim=True, 
#		bake_anim_use_all_bones=True, 
#		bake_anim_use_nla_strips=True, 
#		bake_anim_use_all_actions=True, 
#		bake_anim_force_startend_keying=True, 
#		bake_anim_step=1, 
#		bake_anim_simplify_factor=1, 
#		path_mode='AUTO', 
#		embed_textures=False, 
#		batch_mode='OFF', 
#		use_batch_own_dir=True, 
#		use_metadata=True, 
#		axis_forward='-Z', 
#		axis_up='Y')