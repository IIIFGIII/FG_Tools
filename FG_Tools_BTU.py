bl_info = {
	"name": "BTU",
	"author": "FG_Tools",
	"version": (1, 0),
	"blender": (2, 80, 0),
	"location": "Viev3D > N panel > BTU",
	"description": "Simple tools for transfering objects to Unreal Engine",
	"warning": "",
	"wiki_url": "https://github.com/IIIFGIII/FG_Tools",
	"category": "FG_Tools",
}

import bpy,os,io,math

# Panel layout ------------------------------------------------------------------------------------------------------------------------------------


class BTU_PT_Panel(bpy.types.Panel):
	bl_label = 'BTU'
	bl_idname = 'BTU_PT_Panel'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FG_Tools'
	bl_context = 'objectmode'

	def draw(self,context):
		layout = self.layout
		col = layout.column(align=True)

		col.prop(context.scene.btu_props, 'btu_exp_path', text= '')
		col.operator('fg.btu_exp_op', icon='EXPORT', text='Export FBX')
		col.operator('fg.btu_copy_obj', icon='COPYDOWN', text='Copy To UE')

class BTU_PT_EXP_Settings(bpy.types.Panel):
	bl_label = 'Export FBX Settings'
	bl_idname = 'BTU_PT_EXP_Settings'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_options = {'DEFAULT_CLOSED'}
	bl_parent_id = 'BTU_PT_Panel'

	def draw(self,context):
		layout = self.layout
		col = layout.column(align=True)

		col.prop(context.scene.btu_props, 'btu_exp_scale', text= 'Export Scale')

		col.prop(context.scene.btu_props, 'btu_exp_apptra', text= 'Apply Object Transforms?')
		if context.scene.btu_props.btu_exp_apptra:
			col.prop(context.scene.btu_props, 'btu_exp_apploc', text= 'Apply Location')
			col.prop(context.scene.btu_props, 'btu_exp_approt', text= 'Apply Rotation')
			col.prop(context.scene.btu_props, 'btu_exp_appscl', text= 'Apply Scale')

		col.prop(context.scene.btu_props, 'btu_exp_addpref', text= 'Append prefix?')
		if context.scene.btu_props.btu_exp_addpref:
			col.prop(context.scene.btu_props, 'btu_exp_pref', text= '')

		col.prop(context.scene.btu_props, 'btu_exp_replacedot', text= 'Replace "."?')
		if context.scene.btu_props.btu_exp_replacedot:
			col.prop(context.scene.btu_props, 'btu_exp_replacedotwith', text= '')

		col.prop(context.scene.btu_props, 'btu_exp_remnum', text= 'Remove numeration?')	


class BTU_PT_COP_Settings(bpy.types.Panel):
	bl_label = 'Copy To UE Settings'
	bl_idname = 'BTU_PT_COP_Settings'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_options = {'DEFAULT_CLOSED'}
	bl_parent_id = 'BTU_PT_Panel'

	def draw(self,context):
		layout = self.layout
		col = layout.column(align=True)

		col.prop(context.scene.btu_props, 'btu_copy_scfac', text= 'Units Scale Factor')
		col.prop(context.scene.btu_props, 'btu_copy_offset', text= 'Position Offset')

		col.prop(context.scene.btu_props, 'btu_copy_skiptra', text= 'Skip Object Transforms?')
		if context.scene.btu_props.btu_copy_skiptra:
			col.prop(context.scene.btu_props, 'btu_copy_skiploc', text= 'Skip Location')
			col.prop(context.scene.btu_props, 'btu_copy_skiprot', text= 'Skip Rotation')
			col.prop(context.scene.btu_props, 'btu_copy_skipscl', text= 'Skip Scale')

		col.prop(context.scene.btu_props, 'btu_copy_addpref', text= 'Append prefix?')
		if context.scene.btu_props.btu_copy_addpref:
			col.prop(context.scene.btu_props, 'btu_copy_pref', text= '')

		col.prop(context.scene.btu_props, 'btu_copy_replacedot', text= 'Replace "."?')
		if context.scene.btu_props.btu_copy_replacedot:
			col.prop(context.scene.btu_props, 'btu_copy_replacedotwith', text= '')

		col.prop(context.scene.btu_props, 'btu_copy_meshpath_b', text= 'Path to mesh?')
		if context.scene.btu_props.btu_copy_meshpath_b:
			col.prop(context.scene.btu_props, 'btu_copy_usenum', text= 'Use numeration?')	
			col.prop(context.scene.btu_props, 'btu_copy_meshpath', text= '')



# Exporter -------------------------------------------------------------------------------------------------------------------------------------------

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
		#Reject execute --------------------------------------------------------------------------

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
		#Reject execute ----------------------------------------------------------------------------

		# Exporter loop body

		ob_act = bpy.context.view_layer.objects.active
		bpy.ops.object.select_all(action='DESELECT')
		obj_num = 0 

		for name in selected_obj_names:

			bpy.data.objects[name].select_set(True)
			bpy.ops.object.duplicate()

			if context.scene.btu_props.btu_exp_apptra:
				if context.scene.btu_props.btu_exp_apploc:
					if not context.scene.btu_props.btu_exp_approt:
						bpy.ops.object.rotation_clear()
					if not context.scene.btu_props.btu_exp_appscl:
						bpy.ops.object.scale_clear()
					bpy.ops.apply.transformlocrotscale(option='LOC')


				if context.scene.btu_props.btu_exp_approt:
					if not context.scene.btu_props.btu_exp_apploc:
						bpy.ops.object.location_clear()
					if not context.scene.btu_props.btu_exp_appscl:
						bpy.ops.object.scale_clear()
					bpy.ops.apply.transformlocrotscale(option='ROT')

				if context.scene.btu_props.btu_exp_appscl:
					if not context.scene.btu_props.btu_exp_apploc:
						bpy.ops.object.location_clear()
					if not context.scene.btu_props.btu_exp_approt:
						bpy.ops.object.rotation_clear()
					bpy.ops.apply.transformlocrotscale(option='SCALE')


			if context.scene.btu_props.btu_exp_addpref:
				name = context.scene.btu_props.btu_exp_pref + name
			if context.scene.btu_props.btu_exp_remnum:
				if name.find('.') != -1:
					name = name[:name.rfind(".") + 1]
			if context.scene.btu_props.btu_exp_replacedot:
				if name.find('.') != -1:
					name = name.replace('.',context.scene.btu_props.btu_exp_replacedotwith)
				else:
					name = name + context.scene.btu_props.btu_exp_replacedotwith

			comb_exp_path = exp_folder + name + '.fbx'

			bpy.ops.export_scene.fbx(

				filepath=comb_exp_path,

				use_selection=True, 
				object_types={'MESH'},

				apply_unit_scale=True,
				bake_space_transform=True,
				axis_forward='Y',
				axis_up='Z',
				global_scale=exp_scale,

				mesh_smooth_type='EDGE',

				bake_anim=False

				)

			bpy.ops.object.delete()
			bpy.ops.object.select_all(action='DESELECT')
			obj_num += 1


		# Recover selection, filter mesh objects only	
		for name in selected_obj_names:
			bpy.data.objects[name].select_set(True)

		bpy.context.view_layer.objects.active = ob_act

		self.report({'INFO'}, f'Exported {obj_num} objects to {exp_folder}')
		return{'FINISHED'}

# Copy To Unreal ---------------------------------------------------------------------------------------------------------------------------------

class BTU_Copy_Objects(bpy.types.Operator):
	bl_idname = 'fg.btu_copy_obj'
	bl_label = 'COPY_Operator'
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = 'Copy selected objects data to clipboard for pasting in to UE.'

	def execute(self, context):

		if len(bpy.context.selected_objects) != 0:

			obj_num = 0

			mesh_p = '/Engine/EditorMeshes/'
			mesh_n = 'EditorCube.EditorCube'

			bpy.context.window_manager.clipboard = ''

			out_ob_data = io.StringIO()
			out_ob_data.write("Begin Map\n\tBegin Level\n\n")

			for sob in bpy.context.selected_objects:

				sob_n = sob.name

				sc_fac = context.scene.btu_props.btu_copy_scfac
				offset = context.scene.btu_props.btu_copy_offset

				out_ob_data.write("\t\tBegin Actor Class=/Script/Engine.StaticMeshActor\n")
				out_ob_data.write("\t\t\tBegin Object Class=/Script/Engine.StaticMeshComponent Name=\"StaticMeshComponent0\" Archetype=StaticMeshComponent'/Script/Engine.Default__StaticMeshActor:StaticMeshComponent0'\n")
				out_ob_data.write("\t\t\tEnd Object\n")
				out_ob_data.write("\t\t\t\tBegin Object Name=\"StaticMeshComponent0\"\n")

				if context.scene.btu_props.btu_copy_addpref:
					sob_n = context.scene.btu_props.btu_copy_pref + sob_n

				sob_asn = sob_n

				if not context.scene.btu_props.btu_copy_usenum:
					if sob_n.find('.') != -1:
						sob_asn = sob_asn[:sob_asn.rfind(".") + 1]

				if context.scene.btu_props.btu_copy_replacedot:
					if sob_n.find('.') != -1:
						sob_n = sob_n.replace('.',context.scene.btu_props.btu_copy_replacedotwith)
						sob_asn = sob_asn.replace('.',context.scene.btu_props.btu_copy_replacedotwith)
					else:
						sob_n = sob_n + context.scene.btu_props.btu_copy_replacedotwith
						sob_asn = sob_asn + context.scene.btu_props.btu_copy_replacedotwith

				if context.scene.btu_props.btu_copy_meshpath_b:
					mesh_p = context.scene.btu_props.btu_copy_meshpath
					mesh_n = sob_asn + '.' + sob_asn

				out_ob_data.write("\t\t\t\t\tStaticMesh=StaticMesh'\"%s%s\"'\n" % (str(mesh_p), str(mesh_n)))

				sob_loc = sob.location
				sob_rot = (sob.rotation_euler[0], sob.rotation_euler[1], sob.rotation_euler[2])
				sob_scl = sob.scale

				if context.scene.btu_props.btu_copy_skiptra:
					if context.scene.btu_props.btu_copy_skiploc:
						sob_loc = (0.0, 0.0, 0.0)
					if context.scene.btu_props.btu_copy_skiprot:
						sob_rot = (0.0, 0.0, 0.0)
					if context.scene.btu_props.btu_copy_skipscl:
						sob_scl = (1.0, 1.0, 1.0)

				out_ob_data.write(("\t\t\t\t\tRelativeLocation=(X=%f,Y=%f,Z=%f)\n") % ((sob_loc[0] * sc_fac) + offset[0], ((sob_loc[1] * sc_fac) * -1) + offset[1], (sob_loc[2] * sc_fac) + offset[2]))
				out_ob_data.write(("\t\t\t\t\tRelativeRotation=(Pitch=%.5f,Yaw=%.5f,Roll=%.5f)\n") % (math.degrees(sob_rot[1]) * -1, math.degrees(sob_rot[2]) * -1, math.degrees(sob_rot[0])))
				out_ob_data.write(("\t\t\t\t\tRelativeScale3D=(X=%f,Y=%f,Z=%f)\n") % (sob_scl[0], sob_scl[1], sob_scl[2]))
				out_ob_data.write("\t\t\t\tEnd Object\n\n")
				out_ob_data.write("\t\t\tStaticMeshComponent=\"StaticMeshComponent0\"\n")
				out_ob_data.write("\t\t\tRootComponent=\"StaticMeshComponent0\"\n")
				out_ob_data.write("\t\t\tActorLabel=\"%s\"\n" % str(sob_n))
				out_ob_data.write("\t\tEnd Actor\n\n")

				obj_num += 1

			out_ob_data.write("\n\tEnd Level\nEnd Map\n\n")
			bpy.context.window_manager.clipboard = out_ob_data.getvalue()

			out_ob_data.close()

			self.report({'INFO'}, f'Copied to clipboard {obj_num} objects.')
			return{'FINISHED'}	

		self.report({'ERROR'}, f' No objects selected ... ')
		return{'FINISHED'}

#Addon Properties --------------------------------------------------------------------------------------------------------------------------------

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

	# Export FBX properties ------------------------------------

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

	btu_exp_addpref: bpy.props.BoolProperty(
		name='',
		description="Append prefix to object name for FBX file name.",
		default=False)
	btu_exp_pref: bpy.props.StringProperty(
		name='Prefix to append to object name.', 
		default='SM_')

	btu_exp_replacedot: bpy.props.BoolProperty(
		name='',
		description='Replace " . " (dots) in object names for FBX files names. If object name has no " . " it append suffix',
		default=False)
	btu_exp_replacedotwith: bpy.props.StringProperty(
		name='Character to replace dot. By default "nothing"(remove dot).', 
		default='')

	btu_exp_remnum: bpy.props.BoolProperty(
		name='',
		description=' Will remove numbers after " . ".',
		default=False)

	# Copy to UE properties --------------------------------

	btu_copy_scfac: bpy.props.FloatProperty(
		description='Scale factor. Example: from Blender with meters units scene to UE (default units centimeters) 1m -> 100cm = 100', 
		default=100.0, 
		min=0.001, 
		max=1000.0, 
		step=0.01)
	btu_copy_offset: bpy.props.FloatVectorProperty(
		description='Add N units ( default UE units - cantimiters ) to X, Y, Z location. Useful for workflows with levels offset and not only.', 
		default=(0.0,0.0,0.0),
		precision=6)

	btu_copy_skiptra: bpy.props.BoolProperty(
		name='',
		description="Skip objects transforms.",
		default=False)
	btu_copy_skiploc: bpy.props.BoolProperty(
		name='',
		description="Skip objects lacations ( use 0,0,0 instead )",
		default=False)
	btu_copy_skiprot: bpy.props.BoolProperty(
		name='',
		description="Skip objects rotations ( use 0,0,0 instead )",
		default=False)
	btu_copy_skipscl: bpy.props.BoolProperty(
		name='',
		description="Skip objects scales ( use 1,1,1 instead )",
		default=False)

	btu_copy_addpref: bpy.props.BoolProperty(
		name='',
		description="Append prefix to object name to copy and paste in UE. New namr will also be used to search for asset.",
		default=False)
	btu_copy_pref: bpy.props.StringProperty(
		name='Prefix to append to object name.', 
		default='SM_')

	btu_copy_replacedot: bpy.props.BoolProperty(
		name='',
		description='Replace " . " (dots) in object names copied for ue UE. If object name has no " . " it append suffix',
		default=False)
	btu_copy_replacedotwith: bpy.props.StringProperty(
		name='Character to replace dot. By default "nothing"(remove dot).', 
		default='')
	
	btu_copy_meshpath_b: bpy.props.BoolProperty(
		name='',
		description='Use folder path to search for asset when paste to UE.',
		default=False)
	btu_copy_usenum: bpy.props.BoolProperty(
		name='',
		description='Use numbers after " . " while check for asset in custom location.',
		default=False)
	btu_copy_meshpath: bpy.props.StringProperty(
		name='Unreal folder path with assets to use while pasting. You can copy such path from UE reference viewer. Example: /Game/Mesh/', 
		default='/Game/Mesh/')


#Register/Unregister  ----------------------------------------------------------------------------------------------------------------------------

CTR = [
	BTU_PT_Panel,
	BTU_PT_EXP_Settings,
	BTU_PT_COP_Settings,
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

#FBX exporter variables defaults reminder -----------------------------------------------------------------------------------------------------

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
