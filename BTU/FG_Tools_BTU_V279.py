bl_info = {
	"name": "BTU",
	"author": "IIIFGIII (discord IIIFGIII#7758)",
	"version": (1, 0),
	"blender": (2, 79, 0),
	"location": " T panel > FGT_BTU",
	"description": "Simple tools for transfering objects to Unreal Engine",
	"warning": "Tested/guaranteed work only on official 2.79b (https://download.blender.org/release/Blender2.79/)",
	"wiki_url": "https://github.com/IIIFGIII/FG_Tools/wiki/BTU-Info",
	"category": "FG_Tools",
}

import bpy,os,io,math

#Panel Layout

class BTU_PT_Panel(bpy.types.Panel):
	bl_label = 'BTU'
	bl_idname = 'BTU_PT_Panel'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_category = 'FGT_BTU'
	bl_context = 'objectmode'

	def draw(self, context):
		layout = self.layout
		col = layout.column(align=True)
		btu_p = context.scene.btu_props

		col.prop(btu_p, 'btu_exp_path', text= '')
		col.operator('fgt.btu_exp_op', icon='EXPORT', text='Export FBX')
		col.operator('fgt.btu_copy_obj', icon='COPYDOWN', text='Copy To UE')

class BTU_PT_EXP_Settings(bpy.types.Panel):
	bl_label = 'Export FBX Settings'
	bl_idname = 'BTU_PT_EXP_Settings'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_category = 'FGT_BTU'
	bl_options = {'DEFAULT_CLOSED'}
	bl_parent_id = 'BTU_PT_Panel'

	def draw(self, context):
		layout = self.layout
		col = layout.column(align=True)
		btu_p = context.scene.btu_props

		col.prop(btu_p, 'btu_exp_scale', text= 'Export Scale Factor')

		col.prop(btu_p, 'btu_exp_apptra', text= 'Apply Object Transforms?')
		if btu_p.btu_exp_apptra:
			col.prop(btu_p, 'btu_exp_apploc', text= 'Apply Location')
			col.prop(btu_p, 'btu_exp_approt', text= 'Apply Rotation')
			col.prop(btu_p, 'btu_exp_appscl', text= 'Apply Scale')

		col.prop(btu_p, 'btu_exp_addpref', text= 'Append Prefix?')
		if btu_p.btu_exp_addpref:
			col.prop(btu_p, 'btu_exp_pref', text= '')

		col.prop(btu_p, 'btu_exp_replacedot', text= 'Replace "."?')
		if btu_p.btu_exp_replacedot:
			col.prop(btu_p, 'btu_exp_replacedotwith', text= '')

		col.prop(btu_p, 'btu_exp_remnum', text= 'Remove Numeration?')

class BTU_PT_COP_Settings(bpy.types.Panel):
	bl_label = 'Copy To UE Settings'
	bl_idname = 'BTU_PT_COP_Settings'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'TOOLS'
	bl_category = 'FGT_BTU'
	bl_options = {'DEFAULT_CLOSED'}
	bl_parent_id = 'BTU_PT_Panel'

	def draw(self,context):
		layout = self.layout
		col = layout.column(align=True)
		btu_p = context.scene.btu_props

		col.prop(btu_p, 'btu_copy_scfac', text= 'Units Scale Factor')

		col.prop(btu_p, 'btu_copy_addoffset', text= 'Add Offset?')
		if btu_p.btu_copy_addoffset:
			col.prop(btu_p, 'btu_copy_offset', text= 'Location Offset')

		col.prop(btu_p, 'btu_copy_skiptra', text= 'Skip Object Transforms?')
		if btu_p.btu_copy_skiptra:
			col.prop(btu_p, 'btu_copy_skiploc', text= 'Skip Location')
			col.prop(btu_p, 'btu_copy_skiprot', text= 'Skip Rotation')
			col.prop(btu_p, 'btu_copy_skipscl', text= 'Skip Scale')

		col.prop(btu_p, 'btu_copy_addpref', text= 'Append Prefix?')
		if btu_p.btu_copy_addpref:
			col.prop(btu_p, 'btu_copy_pref', text= '')

		col.prop(btu_p, 'btu_copy_replacedot', text= 'Replace "."?')
		if btu_p.btu_copy_replacedot:
			col.prop(btu_p, 'btu_copy_replacedotwith', text= '')

		col.prop(btu_p, 'btu_copy_meshpath_b', text= 'Path To Mesh?')
		if btu_p.btu_copy_meshpath_b:
			col.prop(btu_p, 'btu_copy_usenum', text= 'Use Numeration?')	
			col.prop(btu_p, 'btu_copy_meshpath', text= '')


# Exporter

class BTU_OT_Expop(bpy.types.Operator):
	bl_idname = 'fgt.btu_exp_op'
	bl_label = 'EXPORT_Operator'
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = 'Export individual .fbx for each object in selection (filter mesh objects only!!!)'


	def execute(self, context):
		selected_obj_names=[]
		btu_p = context.scene.btu_props

		for obj in bpy.context.selected_objects:
			if obj.type == 'MESH':
				selected_obj_names.append(obj.name)

		if not selected_obj_names:
			self.report({'ERROR'}, ' No mesh objects in selection!')
			return{'FINISHED'}
			# Reject execute

		# Check custom path -> rollback to default if wrong
		if btu_p.btu_exp_path != '//Export/':
			exp_folder = bpy.path.abspath(btu_p.btu_exp_path)
			if not os.path.exists(exp_folder):
				self.report({'ERROR'}, ' Your custom path {} not exist! Trying default "//Export/" path.'.format(btu_p.btu_exp_path))		
				context.scene['btu_props']['btu_exp_path'] = '//Export/'

		# Check default path
		if btu_p.btu_exp_path == '//Export/':
			if (bpy.path.abspath('//') != ''):
				exp_folder = bpy.path.abspath(btu_p.btu_exp_path)
				if not os.path.exists(exp_folder):
					os.makedirs(exp_folder)
			else:
				self.report({'ERROR'}, ' Save .blend file somewhere or choose folder for export.')
				return{'FINISHED'}
				# Reject execute


		# Exporter loop body
		ob_act = bpy.context.scene.objects.active
		bpy.ops.object.select_all(action='DESELECT')
		obj_num = 0

		for name in selected_obj_names:

			bpy.data.objects[name].select = True
			bpy.context.scene.objects.active = bpy.data.objects[name]
			bpy.ops.object.duplicate()
			bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

			if btu_p.btu_exp_apptra:
				if btu_p.btu_exp_apploc:
					if not btu_p.btu_exp_approt:
						bpy.ops.object.rotation_clear()
					if not btu_p.btu_exp_appscl:
						bpy.ops.object.scale_clear()
					bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
				else:
					bpy.ops.object.location_clear()


				if btu_p.btu_exp_approt:
					if not btu_p.btu_exp_apploc:
						bpy.ops.object.location_clear()
					if not btu_p.btu_exp_appscl:
						bpy.ops.object.scale_clear()
					bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
				else:
					bpy.ops.object.rotation_clear()

				if btu_p.btu_exp_appscl:
					if not btu_p.btu_exp_apploc:
						bpy.ops.object.location_clear()
					if not btu_p.btu_exp_approt:
						bpy.ops.object.rotation_clear()
					bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
				else:
					bpy.ops.object.scale_clear()

			else:
				bpy.ops.object.location_clear()
				bpy.ops.object.rotation_clear()
				bpy.ops.object.scale_clear()


			if btu_p.btu_exp_addpref:
				name = btu_p.btu_exp_pref + name

			if btu_p.btu_exp_remnum:
				if name.find('.') != -1:
					name = name[:name.rfind(".") + 1]

			if btu_p.btu_exp_replacedot:
				if name.find('.') != -1:
					name = name.replace('.',btu_p.btu_exp_replacedotwith)

			comb_exp_path = exp_folder + name + '.fbx'
			bpy.ops.export_scene.fbx(

				filepath=comb_exp_path,

				use_selection=True, 
				object_types={'MESH'},

				apply_unit_scale=True,
				bake_space_transform=True,
				axis_forward='Y',
				axis_up='Z',
				global_scale=btu_p.btu_exp_scale,

				mesh_smooth_type='EDGE',

				bake_anim=False

				)
			# Remove temp object/mesh data
			d_name = bpy.context.object.data.name
			bpy.ops.object.delete()
			bpy.data.meshes.remove(bpy.data.meshes[d_name])

			bpy.ops.object.select_all(action='DESELECT')
			obj_num += 1

		# Recover selection, filter mesh objects only	
		for name in selected_obj_names:
			bpy.data.objects[name].select = True
		bpy.context.scene.objects.active = ob_act

		self.report({'INFO'}, 'Exported {} objects to {}'.format(obj_num,exp_folder))
		return{'FINISHED'}

# Copy to Unreal

class BTU_OT_Copy_Objects(bpy.types.Operator):
	bl_idname = 'fgt.btu_copy_obj'
	bl_label = 'COPY_Operator'
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = 'Copy selected objects data to clipboard for pasting in to UE'

	def execute(self, context):
		btu_p = context.scene.btu_props

		if len(bpy.context.selected_objects) != 0:

			mesh_p = '/Engine/EditorMeshes/'
			mesh_n = 'EditorCube.EditorCube'

			bpy.context.window_manager.clipboard = ''

			out_ob_data = io.StringIO()
			out_ob_data.write("Begin Map\n\tBegin Level\n\n")

			selected_obj_names=[]
			for obj in bpy.context.selected_objects:
				selected_obj_names.append(obj.name)

			ob_act = bpy.context.scene.objects.active
			bpy.ops.object.select_all(action='DESELECT')
			obj_num = 0

			for name in selected_obj_names:

				sob_n = name

				sc_fac = btu_p.btu_copy_scfac
				offset = btu_p.btu_copy_offset

				out_ob_data.write("\t\tBegin Actor Class=/Script/Engine.StaticMeshActor\n")
				out_ob_data.write("\t\t\tBegin Object Class=/Script/Engine.StaticMeshComponent Name=\"StaticMeshComponent0\" Archetype=StaticMeshComponent'/Script/Engine.Default__StaticMeshActor:StaticMeshComponent0'\n")
				out_ob_data.write("\t\t\tEnd Object\n")
				out_ob_data.write("\t\t\t\tBegin Object Name=\"StaticMeshComponent0\"\n")

				if btu_p.btu_copy_addpref:
					sob_n = btu_p.btu_copy_pref + sob_n

				sob_asn = sob_n

				if not btu_p.btu_copy_usenum:
					if sob_n.find('.') != -1:
						sob_asn = sob_asn[:sob_asn.rfind(".") + 1]

				if btu_p.btu_copy_replacedot:
					if sob_n.find('.') != -1:
						sob_n = sob_n.replace('.',btu_p.btu_copy_replacedotwith)
						sob_asn = sob_asn.replace('.',btu_p.btu_copy_replacedotwith)

				if btu_p.btu_copy_meshpath_b:
					mesh_p = btu_p.btu_copy_meshpath
					mesh_n = sob_asn + '.' + sob_asn

				out_ob_data.write("\t\t\t\t\tStaticMesh=StaticMesh'\"%s%s\"'\n" % (str(mesh_p), str(mesh_n)))

				# Temporary objects to copy applied parent transforms
				bpy.data.objects[name].select = True
				bpy.context.scene.objects.active = bpy.data.objects[name]
				bpy.ops.object.duplicate()
				bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
				sob = bpy.context.scene.objects.active

				sob_loc = sob.location
				sob_rot = (sob.rotation_euler[0], sob.rotation_euler[1], sob.rotation_euler[2])
				sob_scl = sob.scale

				# Remove temporary object/mesh data
				d_name = bpy.context.object.data.name
				bpy.ops.object.delete()
				bpy.data.meshes.remove(bpy.data.meshes[d_name])
				bpy.ops.object.select_all(action='DESELECT')

				if not btu_p.btu_copy_addoffset:
					offset = (0.0,0.0,0.0)

				if not btu_p.btu_copy_skiploc or not btu_p.btu_copy_skiptra:
					out_ob_data.write(("\t\t\t\t\tRelativeLocation=(X=%f,Y=%f,Z=%f)\n") % ((sob_loc[0] * sc_fac) + offset[0], ((sob_loc[1] * sc_fac) * -1) + offset[1], (sob_loc[2] * sc_fac) + offset[2]))
				if not btu_p.btu_copy_skiprot or not btu_p.btu_copy_skiptra:
					out_ob_data.write(("\t\t\t\t\tRelativeRotation=(Pitch=%.5f,Yaw=%.5f,Roll=%.5f)\n") % (math.degrees(sob_rot[1]) * -1, math.degrees(sob_rot[2]) * -1, math.degrees(sob_rot[0])))
				if not btu_p.btu_copy_skipscl or not btu_p.btu_copy_skiptra:
					out_ob_data.write(("\t\t\t\t\tRelativeScale3D=(X=%f,Y=%f,Z=%f)\n") % (sob_scl[0], sob_scl[1], sob_scl[2]))

				out_ob_data.write("\t\t\t\tEnd Object\n\n")
				out_ob_data.write("\t\t\tStaticMeshComponent=\"StaticMeshComponent0\"\n")
				out_ob_data.write("\t\t\tRootComponent=\"StaticMeshComponent0\"\n")
				out_ob_data.write("\t\t\tActorLabel=\"%s\"\n" % str(sob_n))
				out_ob_data.write("\t\tEnd Actor\n\n")

				obj_num += 1

			# Recover selection
			for name in selected_obj_names:
				bpy.data.objects[name].select = True
			bpy.context.scene.objects.active = ob_act

			out_ob_data.write("\n\tEnd Level\nEnd Map\n\n")
			bpy.context.window_manager.clipboard = out_ob_data.getvalue()

			out_ob_data.close()

			self.report({'INFO'}, 'Copied to clipboard {} objects.'.format(obj_num))
			return{'FINISHED'}	

		self.report({'ERROR'}, ' No objects selected ... ')
		return{'FINISHED'}

class BTU_Settings_Props(bpy.types.PropertyGroup):
	btu_exp_path = bpy.props.StringProperty(
		name='Export folder path. // expression is relative to file location(not work if file not saved)', 
		default='//Export/', 
		subtype='DIR_PATH')	

	btu_exp_scale = bpy.props.FloatProperty(
		description='Will export models with this scale factor', 
		default=1.0, 
		min=0.001, 
		max=1000.0, 
		step=0.01)

	# Export FBX properties

	btu_exp_apptra = bpy.props.BoolProperty(
		name='',
		description='Apply object transforms',
		default=False)
	btu_exp_apploc = bpy.props.BoolProperty(
		name='',
		description="Apply object location - bpy.ops.apply.transformlocrotscale(option='LOC')",
		default=False)
	btu_exp_approt = bpy.props.BoolProperty(
		name='',
		description="Apply object rotation - bpy.ops.apply.transformlocrotscale(option='ROT')",
		default=False)
	btu_exp_appscl = bpy.props.BoolProperty(
		name='',
		description="Apply object scale - bpy.ops.apply.transformlocrotscale(option='SCALE')",
		default=False)

	btu_exp_addpref = bpy.props.BoolProperty(
		name='',
		description='Append prefix to object name for FBX file name',
		default=False)
	btu_exp_pref = bpy.props.StringProperty(
		name='Prefix to append to object name', 
		default='SM_')

	btu_exp_replacedot = bpy.props.BoolProperty(
		name='',
		description='Replace " . " (dot) in object name for FBX file name',
		default=False)
	btu_exp_replacedotwith = bpy.props.StringProperty(
		name='Character to replace " . " (dot). By default "nothing"(remove dot)', 
		default='')

	btu_exp_remnum = bpy.props.BoolProperty(
		name='',
		description='Will remove numbers after " . "(dot)',
		default=False)

	# Copy to UE properties

	btu_copy_scfac = bpy.props.FloatProperty(
		description='Scale factor. Example: from Blender with scene units meters -> to UE (default units centimeters) 1m -> 100cm = 100', 
		default=100.0, 
		min=0.001, 
		max=1000.0, 
		step=0.01)
	btu_copy_addoffset = bpy.props.BoolProperty(
		name='',
		description='Add "location offset" values to object location',
		default=False)
	btu_copy_offset = bpy.props.FloatVectorProperty(
		description='Add N units (default UE units - cantimiters) to X, Y, Z location. Useful for workflows with levels offset and not only', 
		default=(0.0,0.0,0.0),
		precision=6)

	btu_copy_skiptra = bpy.props.BoolProperty(
		name='',
		description='Skip object transforms',
		default=False)
	btu_copy_skiploc = bpy.props.BoolProperty(
		name='',
		description='Skip object location (use 0,0,0 instead)',
		default=False)
	btu_copy_skiprot = bpy.props.BoolProperty(
		name='',
		description='Skip object rotation (use 0,0,0 instead)',
		default=False)
	btu_copy_skipscl = bpy.props.BoolProperty(
		name='',
		description='Skip object scale (use 1,1,1 instead)',
		default=False)

	btu_copy_addpref = bpy.props.BoolProperty(
		name='',
		description='Append prefix to object name to copy and paste in UE. New name will also be used to search for asset',
		default=False)
	btu_copy_pref = bpy.props.StringProperty(
		name='Prefix to append to object name', 
		default='SM_')

	btu_copy_replacedot = bpy.props.BoolProperty(
		name='',
		description='Replace " . " (dot) in object name copied to ue UE',
		default=False)
	btu_copy_replacedotwith = bpy.props.StringProperty(
		name='Character to replace " . " (dot). By default "nothing"(remove dot)', 
		default='')
	
	btu_copy_meshpath_b = bpy.props.BoolProperty(
		name='',
		description='Use custom folder path to search for asset when paste to UE. If not - you will paste default UE box mesh',
		default=False)
	btu_copy_usenum = bpy.props.BoolProperty(
		name='',
		description='Use numbers after " . " (dot) while check for asset in custom location. Otherwise skip numbers',
		default=False)
	btu_copy_meshpath = bpy.props.StringProperty(
		name='Unreal project folder path with assets to use while pasting. You can copy such path from UE reference viewer. Example: /Game/Mesh/', 
		default='/Game/Mesh/')

# Register/Unregister

CTR = [
	BTU_PT_Panel,
	BTU_PT_EXP_Settings,
	BTU_OT_Expop,
	BTU_OT_Copy_Objects,
	BTU_Settings_Props,
	BTU_PT_COP_Settings,

]

def register():
	for cls in CTR:
		bpy.utils.register_class(cls)
	# Register properties
	bpy.types.Scene.btu_props = bpy.props.PointerProperty(type=BTU_Settings_Props)

def unregister():
	for cls in CTR:
		bpy.utils.unregister_class(cls)
	# Delete properties
	del bpy.types.Scene.btu_props
