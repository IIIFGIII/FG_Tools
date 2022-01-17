bl_info = {
	"name": "SOT",
	"author": "IIIFGIII (Discord IIIFGIII#7758)",
	"version": (1, 2),
	"blender": (2, 83, 0),
	"location": "Viev3D > N panel > FGT > SOT",
	"description": "Set Origin Transform (SOT) tool. Tested on versions 2.83.18 and 2.93.4. For bug report/feedback contact me in Discord.",
	"warning": "",
	"wiki_url": "https://github.com/IIIFGIII/FG_Tools",
	"category": "FG_Tools",
}

import bpy, bmesh, math, bgl, gpu, time
import numpy as np
import mathutils as mu
from gpu_extras.batch import batch_for_shader

bpr = bpy.props


pr_values = {}
sob_mts = {}
spot_orient_matrix = mu.Matrix.Identity(3)
nvdata = np.empty(0, dtype=np.float32)
mnvdata = []
svdata = np.empty(0, dtype=np.float32)
msvdata = []
sps_data = []
rot_update = 0 
loc_mode_current = '1'

spot_mode_space_check = None
spot_projection_check = None
spot_sob_matrices_vdata = []
spot_orient_matrix = None
spot_sps_data = []
spot_psp_data = []

shapes = [
	[(-0.2,0,0),(-0.05,0,0), (0.05,0,0),(0.2,0,0), (0,0,0),(-0.1,0.1,0), (-0.1,0.1,0),(0.1,0.1,0), (0.1,0.1,0),(0,0,0)],
	[(-0.1,-0.1,0),(-0.1,0.1,0), (-0.1,0.1,0),(0.1,0.1,0), (0.1,0.1,0),(0.1,-0.1,0), (0.1,-0.1,0),(-0.1,-0.1,0)],
	[(-0.1,0,0),(0,0.1,0), (0,0.1,0),(0.1,0,0), (0.1,0,0),(0,-0.1,0), (0,-0.1,0),(-0.1,0,0)],
	[(-0.1,-0.1,0),(0,0,0), (0,0,0),(0.1,-0.1,0), (0.1,-0.1,0),(-0.1,-0.1,0)],
	[(0.2,0.2,0),(0.05,0.05,0), (-0.2,0.2,0),(-0.05,0.05,0), (-0.2,-0.2,0),(-0.05,-0.05,0), (0.2,-0.2,0),(0.05,-0.05,0),]]

#Colors = white spots, border mesh spot, bound center spot, center of mass spot, 
#		  X, Y, Z axis 
#		  bound front/back
# 		  drop point , drop lines A,B,C
colors = [(1.0, 1.0, 1.0, 1.0),(0, 0.9, 1.0, 1.0),(0.9, 0.2, 0.2, 1.0),(1.0, 0.5, 0.05, 1.0),
		   (1.0, 0.2, 0.2, 1.0),(0.4, 1, 0.0, 1.0),(0.0 , 0.5, 1.0, 1.0),
		   (1.0, 0.85, 0.15, 1.0),(0.6, 0.5, 0.2, 1.0),
		   (1.0, 0.1, 0.8, 1.0), (1.0, 0.65, 0.95, 1.0), (0.6, 0.6, 0.6, 1.0)]

grid = [(-2,2.25,0),(-2,-2.25,0), (-1,2.25,0),(-1,-2.25,0), (0,2.25,0),(0,-2.25,0), (1,2.25,0),(1,-2.25,0), (2,2.25,0),(2,-2.25,0),
		(2.25,-2,0),(-2.25,-2,0), (2.25,-1,0),(-2.25,-1,0), (2.25,0,0),(-2.25,0,0), (2.25,1,0),(-2.25,1,0), (2.25,2,0),(-2.25,2,0)]

axis_base =[((-1.5,0,0),(colors[4])),((1.5,0,0),(colors[4])),
			((1.4,0.1,0.1),(colors[4])),((1.5,0,0),(colors[4])),
			((1.4,0.1,-0.1),(colors[4])),((1.5,0,0),(colors[4])),
			((1.4,-0.1,-0.1),(colors[4])),((1.5,0,0),(colors[4])),
			((1.4,-0.1,0.1),(colors[4])),((1.5,0,0),(colors[4])),

			((0,-1.5,0),(colors[5])),((0,1.5,0),(colors[5])),
			((0.1,1.4,0.1),(colors[5])),((0,1.5,0),(colors[5])),
			((-0.1,1.4,0.1),(colors[5])),((0,1.5,0),(colors[5])),
			((-0.1,1.4,-0.1),(colors[5])),((0,1.5,0),(colors[5])),
			((0.1,1.4,-0.1),(colors[5])),((0,1.5,0),(colors[5])),

			((0,0,-1.5),(colors[6])),((0,0,1.5),(colors[6])),
			((0.1,0.1,1.4),(colors[6])),((0,0,1.5),(colors[6])),
			((-0.1,0.1,1.4),(colors[6])),((0,0,1.5),(colors[6])),
			((-0.1,-0.1,1.4),(colors[6])),((0,0,1.5),(colors[6])),
			((0.1,-0.1,1.4),(colors[6])),((0,0,1.5),(colors[6]))]


def report(self,message):
	self.report({'ERROR'}, message)
	return{'CANCELLED'}

def unic_name_geterator(name, existing_names, use_exception = False, excepted_name = ''):
	name_is_unic = False
	first_check = True

	while not name_is_unic:
		name_is_unic = True
		for en in existing_names:
			if use_exception and name == excepted_name:
				name_is_unic = True
				break				
			elif first_check and name == en and name[-4] == '.' and name[-3:].isnumeric():
				name = name[:-3] + '001'
				name_is_unic = False
				first_check = False
				break
			elif first_check and name == en: 
				name = name + '.001'
				name_is_unic = False
				first_check = False
				break
			elif name == en:
				num = str(int(name[-3:])+1)
				zeros = '00' if len(num) == 1 else '0'
				num = zeros + num if len(num) != 3 else num 
				name = name[:-3] + num
				name_is_unic = False
				break

	return name	

def combine_matrix_v3(v1,v2,v3):
	mt = mu.Matrix.Identity(3)
	mt.col[0] = v1
	mt.col[1] = v2
	mt.col[2] = v3
	return mt

def Vector(vec):
	return mu.Vector(vec)

def tov4(xyz,w):
	return mu.Vector((xyz[0],xyz[1],xyz[2],w))

def vector_fix(obm,vector):
	return (obm.inverted_safe().transposed().to_3x3() @ vector).normalized()

def distance(va,vb):
	return math.sqrt((vb[0]-va[0])**2+(vb[1]-va[1])**2+(vb[2]-va[2])**2)

def remap(va,vb,ra,rb,rv):
	if va == vb or ra == rb: return va
	else:
		if ra<rb and rv<=ra or ra>rb and rv>=ra: return va
		elif ra<rb and rv>=rb or ra>rb and rv<=rb: return vb
		else: return (va+(((rv-ra)/(rb-ra))*(vb-va)))

def vectors_remap(vx,vy,vz,sot):

	if not sot.z_rem:
		return vx,vy,vz

	xr,yr,zr = vx,vy,vz
	zax = sot.z_axis

	if zax == 'z+':
		rem = sot.rem_zp 
		vz = zr
		if   rem == '1': vx,vy = xr,yr
		elif rem == '2': vx,vy = yr,xr*-1
		elif rem == '3': vx,vy = xr*-1,yr*-1
		elif rem == '4': vx,vy = yr*-1,xr

	elif zax == 'z-':
		rem = sot.rem_zn 
		vz = zr*-1
		if   rem == '1': vx,vy = xr,yr*-1
		elif rem == '2': vx,vy = yr,xr
		elif rem == '3': vx,vy = xr*-1,yr
		elif rem == '4': vx,vy = yr*-1,xr*-1

	elif zax == 'y+':
		rem = sot.rem_yp
		vz = yr
		if   rem == '1': vx,vy = xr,zr*-1
		elif rem == '2': vx,vy = zr,xr
		elif rem == '3': vx,vy = xr*-1,zr
		elif rem == '4': vx,vy = zr*-1,xr*-1

	elif zax == 'y-':
		rem = sot.rem_yn
		vz = yr*-1
		if   rem == '1': vx,vy = xr,zr
		elif rem == '2': vx,vy = zr,xr*-1
		elif rem == '3': vx,vy = xr*-1,zr*-1
		elif rem == '4': vx,vy = zr*-1,xr

	elif zax == 'x+':
		rem = sot.rem_xp
		vz = xr
		if   rem == '1': vx,vy = zr*-1,yr
		elif rem == '2': vx,vy = yr,zr
		elif rem == '3': vx,vy = zr,yr*-1
		elif rem == '4': vx,vy = yr*-1,zr*-1

	elif zax == 'x-':
		rem = sot.rem_xn
		vz = xr*-1
		if   rem == '1':  	vx = zr
		elif rem == '2': vx,vy = yr,zr*-1
		elif rem == '3': vx,vy = zr*-1,yr*-1
		elif rem == '4': vx,vy = yr*-1,zr

	return vx,vy,vz

def object_in_edit(bob,sob_r):
	eob = []
	for ob in sob_r:
		if ob.mode == 'EDIT': eob.append(ob)
		elif ob.mode == 'OBJECT': ob.select_set(False)
	if eob != []: bpy.ops.object.editmode_toggle()
	bob.select_all(action='DESELECT')
	return eob

def recover_edit(eob,bcv,aob_r,sob_r):
	bcv.objects.active = aob_r
	if eob != []:
		for ob in eob: ob.select_set(True)
		bpy.ops.object.editmode_toggle()
	for ob in sob_r: ob.select_set(True)
	return

# def fix_children_loc(x,y,z,tob,bcv,oob):
# 	childrens = [ob for ob in bpy.data.objects if ob.parent == tob]
# 	fix_vector = mu.Vector(tob.matrix_world.col[3][:3]) - mu.Vector((x,y,z))
# 	for tob in childrens:
# 		#if not tob in oob: 
# 		tob.select_set(True)
# 		bpy.ops.transform.translate(value= fix_vector)
# 		tob.select_set(False)
# 		# else:
# 		# 	print(tob.name + 'was ignored in children fix')

def fix_children_clear(tob):
	childrens = [ob for ob in bpy.data.objects if ob.parent == tob]
	for tob in childrens:
		tob.select_set(True)
		bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
		tob.select_set(False)
	return childrens

def fix_children_clear(tob):
	childrens = [ob for ob in bpy.data.objects if ob.parent == tob]
	for tob in childrens:
		tob.select_set(True)
		bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
		tob.select_set(False)
	return childrens

def set_origin_location(x,y,z,tob,bcv,oob=[]):

	childrens = [ob for ob in bpy.data.objects if ob.parent == tob]
	for cob in childrens:
		cob.select_set(True)
		bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
		cob.select_set(False)

	tob.select_set(True)
	bcv.objects.active = tob
	loc = tob.matrix_world.col[3]
	pos = mu.Vector((x,y,z,1))
	dif = mu.Vector((loc - pos)[:3])
	tob.matrix_world.col[3] = pos
	obm = tob.matrix_world
	tmt = mu.Matrix.Identity(4)
	tmt.col[3] = tov4(obm.to_3x3().inverted() @ dif,1)		
	tob.data.transform(tmt)
	if tob.type == 'ARMATURE':
		bpy.ops.object.editmode_toggle()
		bpy.ops.object.editmode_toggle()

	for cob in childrens:
		cob.select_set(True)
		bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
		cob.select_set(False)

	tob.select_set(False)
	return

def set_origin_orientation(x,y,z,tob,bcv,bob):

	childrens = [ob for ob in bpy.data.objects if ob.parent == tob]
	for cob in childrens:
		cob.select_set(True)
		bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
		cob.select_set(False)

	tob.select_set(True)
	bcv.objects.active = tob
	rmt = (mu.Euler((x,y,z),'XYZ')).to_matrix()
	loc = tob.matrix_world.col[3]
	scl = tob.matrix_world.to_scale()
	rmt_m = rmt.to_4x4()
	rmt_m.col[0] = rmt_m.col[0]*scl[0]
	rmt_m.col[1] = rmt_m.col[1]*scl[1]
	rmt_m.col[2] = rmt_m.col[2]*scl[2] 	
	rmt_m.col[3] = loc
	rmt = (tob.matrix_world.to_3x3().inverted() @ rmt).to_4x4()
	rmt.col[0] = rmt.col[0]*scl[0]
	rmt.col[1] = rmt.col[1]*scl[1]
	rmt.col[2] = rmt.col[2]*scl[2]
	tob.data.transform(rmt.inverted())
	tob.matrix_world = rmt_m
	bob.transform_apply(location = False, rotation= False, scale= True,  properties=False)
	if tob.type == 'ARMATURE':
		bpy.ops.object.editmode_toggle()
		bpy.ops.object.editmode_toggle()

	for cob in childrens:
		cob.select_set(True)
		bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)
		cob.select_set(False)

	tob.select_set(False)
	return

def get_preset_loc_rot(sot,loc):
	if pr_values != {}:
		if loc: return pr_values.get(sot.loc_rot_presets)[0]
		else:   return pr_values.get(sot.loc_rot_presets)[1]

def get_cursor_loc_rot(bco,sot,loc):
	mt = bco.scene.cursor.matrix
	if loc:
		return mu.Vector(mt.col[3][:3])
	else:
		mt = mt.to_3x3()
		vx,vy,vz = mu.Vector(mt.col[0]),mu.Vector(mt.col[1]),mu.Vector(mt.col[2])
		vx,vy,vz = vectors_remap(vx,vy,vz,sot)
		return combine_matrix_v3(vx,vy,vz)

def get_element_loc(self,bco,sot,aob):
	bmd = bmesh.from_edit_mesh(bco.edit_object.data)
	bma = bmd.select_history.active

	if bma == None: return report(self,'No active element in selection!!!')
	else:
		obm = aob.matrix_world
		if str(bma).find('BMVert') == 1:
			co = bma.co
		else:
			co = mu.Vector((0,0,0))
			verts = bma.verts
			for v in verts:
				co += v.co
			co = co/len(verts)
		if obm.to_scale() != (1.0,1.0,1.0):
			co = obm @ co
		return co

def get_element_vectors(self,bco,sot,aob):
	bmd = bmesh.from_edit_mesh(bco.edit_object.data)
	bma = bmd.select_history.active
	vzw = mu.Vector((0,0,1))
	obm = aob.matrix_world

	if bma == None: return report(self,'No active element in selection!!!')
	else:
		if str(bma).find('BMVert') == 1:

			# Vertex Normals
			if len(bma.link_faces) == 0:
				vz = vector_fix(obm, (bma.co - mu.Vector(obm.col[3][:3])))
				if vz[2]>0:
					m = -1
				else:
					vzw = vzw*-1
					m = 1
				
				if vzw.dot(vz) > 0.5:
					vy = (vzw - (vzw.dot(vz)*vz)).normalized() * m
				else:
					m = m*-1
					vm = (vz * mu.Vector((1,1,0))).normalized()
					vy = (vm - (vm.dot(vz)*vz)).normalized() * m
				
				if (abs(sum(vy[:]))) == 0:
					if abs(vz[2]) == 1:
						vy = mu.Vector((0,1,0))
					elif vz[2] == 0:
						vy = mu.Vector((0,0,-1))

				vx = (vz.cross(vy))*-1

			else:
				vz = vector_fix(obm, bma.normal)
				if vz[2]>0:
					m = -1
				else:
					vzw = vzw*-1
					m = 1
				
				if vzw.dot(vz) > 0.5:
					vy = (vzw - (vzw.dot(vz)*vz)).normalized() * m
				else:
					m = m*-1
					vm = (vz * mu.Vector((1,1,0))).normalized()
					vy = (vm - (vm.dot(vz)*vz)).normalized() * m

				if (abs(sum(vy[:]))) == 0:
					if abs(vz[2]) == 1:
						vy = mu.Vector((0,1,0))
					elif vz[2] == 0:
						vy = mu.Vector((0,0,-1))

				vx = (vz.cross(vy))*-1

		# Edges Normals
		elif str(bma).find('BMEdge') == 1: 
			vy = vector_fix(obm, (bma.verts[0].co - bma.verts[1].co).normalized())
			if len(bma.link_faces) == 0:
				if vy[2]>0:
					m = -1
				else:
					vzw = vzw*-1
					m = 1

				if vzw.dot(vy) > 0.5:
					vz = (vzw - (vzw.dot(vy)*vy)).normalized() * m
				else:
					m = m*-1
					vm = (vy * mu.Vector((1,1,0))).normalized()
					vz = (vm - (vm.dot(vy)*vy)).normalized() * m
			elif len(bma.link_faces) == 1:
				vz = vector_fix(obm, bma.link_faces[0].normal)
			else:
				vz = ((vector_fix(obm, bma.link_faces[0].normal) + vector_fix(obm, bma.link_faces[1].normal))/2).normalized()

			vx = (vz.cross(vy))*-1

		# Faces Normals
		else: 
			vz = vector_fix(obm, bma.normal)
			print(vz)
			if len(bma.verts)	== 3:
				print('FACE Triangle')
				eils = (sorted([(i,e.calc_length()) for i,e in enumerate(bma.edges)], key=lambda e: e[1]))
				ei = eils[0][0] if eils[1][1] / eils[0][1] > 1.262169 else eils[2][0]
				vy = vector_fix(obm, (bma.edges[ei].verts[0].co - bma.edges[ei].verts[1].co).normalized())
				vy = vy-(vy.dot(vz)*vz)

				#vy = vector_fix(obm, (bma.calc_tangent_edge())*-1)
			elif len(bma.verts) == 4:
				print('FACE Quad')
				vy = vector_fix(obm, ((bma.calc_tangent_edge_pair()).normalized())*-1)
				vy = vy-(vy.dot(vz)*vz)
			else:
				print('FACE Ngon')
				le,ei = 0,-1
				#c = 0 remove
				for i,e in enumerate(bma.edges):
					if e.calc_length() > le: le,ei = e.calc_length(),i
				vy = vector_fix(obm, (bma.edges[ei].verts[0].co - bma.edges[ei].verts[1].co).normalized())
				vy = vy-(vy.dot(vz)*vz)
			vx = (vz.cross(vy))*-1

		#vx,vy,vz = vectors_remap(vx,vy,vz,sot)

		return combine_matrix_v3(vx,vy,vz)

def get_object_loc_rot(self,bco,sot,loc):

	bcv = bco.view_layer
	aob = bcv.objects.active

	if aob == None: return report(self,'No active object in selection!!!')
	else:
		if loc:
			return mu.Vector(aob.matrix_world.col[3][:3])
		else:
			mt = aob.matrix_world.to_3x3().normalized()
			vx,vy,vz = mu.Vector(mt.col[0]),mu.Vector(mt.col[1]),mu.Vector(mt.col[2])
			vx,vy,vz = vectors_remap(vx,vy,vz,sot)
			return combine_matrix_v3(vx,vy,vz)

def set_manual_values(sot,value,param):
	if param == 'loc':
		sot.loc_x,sot.loc_y,sot.loc_z = value
	elif param == 'rot':
		if abs(value[0]) < 0.0001: value[0] = 0
		if abs(value[1]) < 0.0001: value[1] = 0
		if abs(value[2]) < 0.0001: value[2] = 0
		sot.rot_x,sot.rot_y,sot.rot_z = value
	elif param == 'czp':
		sot.czp_x,sot.czp_y,sot.czp_z = value
	return

def aob_check(aob):
	if aob == None: return (True,'No ACTIVE object in selection!!!!')
	else: return (False,'')

def mesh_check(cob):
	if cob.type != 'MESH': return (True,'One of selected objects is not MESH type.')
	else: return (False,'')

def screen_size(bco,loc,pdc):
	s3d = bco.space_data.region_3d
	a3d = bco.area.spaces.active.region_3d

	if s3d.view_perspective == 'ORTHO':
		scl = a3d.view_distance/10
	elif s3d.view_perspective == 'PERSP':
		vmt = a3d.view_matrix
		dis = distance(vmt @ loc,mu.Vector((0,0,0)))
		if dis<30 and pdc:
			scl = abs(dis)/remap(1,10,0,30,dis)
		else:
			scl = abs(dis)/10

	else:
		zo = a3d.view_camera_zoom
		vmt = a3d.view_matrix
		if zo>0:
			v = 3.14**(((30+((zo)+30))/30)*remap(1,0.26,0,1,math.sqrt((zo/600)**0.7)))
		else:
			v = 3.14**((30+((zo)+30))/30)

		dis = distance(vmt @ loc,mu.Vector((0,0,0)))
		if dis<30 and pdc:
			scl = abs(dis)/remap(1,v,0,30,dis)
		else:
			scl = abs(dis)/v

	return scl

def draw_loc_rot_axis_main(self,context):
	bco = bpy.context
	sot = context.scene.sot_props

	vc = [(-0.3, 0.0, 0.0), (-0.1, 0.0, 0.0),
		(0.0, -0.3, 0.0), (0.0, -0.1, 0.0),
		(0.0, 0.0, -0.3), (0.0, 0.0, -0.1),
		(0.1, 0.0, 0.0), (1.0, 0.0, 0.0),
		(0.0, 0.1, 0.0), (0.0, 1.0, 0.0),
		(0.0, 0.0, 0.1), (0.0, 0.0, 1.0)]
	vcm = []

	loc = mu.Vector((sot.loc_x,sot.loc_y,sot.loc_z))
	euler = mu.Euler((sot.rot_x,sot.rot_y,sot.rot_z),'XYZ')
	rot = euler.to_matrix()

	scl = screen_size(bco,loc,False)

	for v in vc:
		v = (rot @ (mu.Vector(v) * scl)) + loc
		vcm.append(v)

	shader = gpu.shader.from_builtin('3D_SMOOTH_COLOR')
	col = [(1.0, 1.0, 1.0, 0.8), (1.0, 1.0, 1.0, 0.8),
		(1.0, 1.0, 1.0, 0.8), (1.0, 1.0, 1.0, 0.8),
		(1.0, 1.0, 1.0, 0.8), (1.0, 1.0, 1.0, 0.8),
		(1.0, 0.0, 0.0, 1.0), (1.0, 0.0, 0.0, 1.0),
		(0.0, 1.0, 0.0, 1.0), (0.0, 1.0, 0.0, 1.0),
		(0.0, 0.0, 1.0, 1.0), (0.0, 0.0, 1.0, 1.0)]

	draw_this(shader,vcm,col,6)
	return

def draw_loc_rot_presets_main(self,context):
	bco = bpy.context
	sot = context.scene.sot_props

	global pr_values
	global colors
	global grid
	global axis_base

	if pr_values != {}:
		prv = pr_values.get(sot.loc_rot_presets)
		loc = mu.Vector(prv[0])
		euler = mu.Euler(prv[1],'XYZ')
		rot = euler.to_matrix()
	else:
		loc = mu.Vector((0,0,0))
		rot = mu.Matrix.Identity(3)

	scl_steps = [(700,500),(60,50),(5,5),(1,1),(0.5,0.5),(0.07,0.125)]
	scl = screen_size(bco,loc,False)
	scli = 1
	if scl>=1:
		for st in scl_steps:
			if scl>=st[0]:
				scli = st[1] 
				break	
	else:
		for st in scl_steps[::-1]:
			if scl<=st[0]:
				scli = st[1] 
				break	


	grid_crd = []
	grid_col = []

	for crd in grid:
		if scli != 1:
			crd = (rot @ (mu.Vector(crd) * scli)) + loc
		else:
			crd = (rot @ mu.Vector(crd)) + loc
		grid_crd.append(crd)
		grid_col.append((1,1,1,1))
		


	axis_crd = []
	axis_col = []

	for cc in axis_base:
		crd = (rot @( mu.Vector(cc[0]) * scl)) + loc
		axis_crd.append(crd)
		axis_col.append(cc[1])		

	shader = gpu.shader.from_builtin('3D_SMOOTH_COLOR')
	draw_this(shader,grid_crd,grid_col)
	draw_this(shader,axis_crd,axis_col,2)
	return

def matrices_vdata_get(spot_set_mode,aob,sob):

	global spot_sob_matrices_vdata
	spot_sob_matrices_vdata.clear()

	if spot_set_mode == '1' or spot_set_mode == '3':
		if aob != None:
			if aob.type == 'MESH':
				if aob.mode == 'EDIT': aob.update_from_editmode()
				v_num = len(aob.data.vertices)
				vdata = np.empty(v_num*3, dtype=np.float32)
				aob.data.vertices.foreach_get('co',vdata)
				vdata = np.reshape(vdata,(v_num,3))
				obm = aob.matrix_world
				for v in range(vdata.shape[0]): vdata[v] = (obm @ mu.Vector(vdata[v]))[:]
				spot_sob_matrices_vdata.append((obm,vdata))

	elif spot_set_mode == '2':
		mvdata = np.empty(0, dtype=np.float32)
		for ob in sob:
			if ob.type == 'MESH':
				if ob.mode == 'EDIT': ob.update_from_editmode()
				v_num = len(ob.data.vertices)
				vdata = np.empty(v_num*3, dtype=np.float32)
				ob.data.vertices.foreach_get('co',vdata)
				vdata = np.reshape(vdata,(v_num,3))
				obm = ob.matrix_world
				for v in range(vdata.shape[0]): vdata[v] = (obm @ mu.Vector(vdata[v]))[:]
				mvdata = np.append(mvdata,vdata)
		mvdata = np.reshape(mvdata, (mvdata.size//3, 3))
		if mvdata != []:
			if aob != None and aob.type == 'MESH': obm = aob.matrix_world
			elif aob != None: obm = aob.matrix_world
			else:
				for ob in sob:
					if ob.type == 'MESH':
						obm = ob.matrix_world
						break
			obm = aob.matrix_world if aob != None else sob[0].matrix_world
			spot_sob_matrices_vdata.append((obm,mvdata))

	else:
		for ob in sob:
			if ob.type == 'MESH':
				if ob.mode == 'EDIT': ob.update_from_editmode()
				v_num = len(ob.data.vertices)
				vdata = np.empty(v_num*3, dtype=np.float32)
				ob.data.vertices.foreach_get('co',vdata)
				vdata = np.reshape(vdata,(v_num,3))
				obm = ob.matrix_world
				for v in range(vdata.shape[0]): vdata[v] = (obm @ mu.Vector(vdata[v]))[:]
				spot_sob_matrices_vdata.append((obm,vdata))

def rotation_matrix_get(spot_set_space,bco,sot,aob,sob):

	global pr_values
	global spot_orient_matrix

	if  spot_set_space == '5' and pr_values == {}:
		spot_set_space = '1' 

	if spot_set_space == '1': # Global
		spot_orient_matrix = mu.Matrix.Identity(3)	
	elif spot_set_space == '2':  # Local
		if not aob_check(aob)[0]:
			spot_orient_matrix = aob.matrix_world.to_3x3().normalized()
		elif 'MESH' in [ob.type for ob in sob]:
			for ob in sob:
				if ob.type == 'MESH':
					spot_orient_matrix = ob.matrix_world.to_3x3().normalized()
					break
		else:
			spot_orient_matrix = mu.Matrix.Identity(3)
	elif spot_set_space == '3': # View
		spot_orient_matrix = bco.area.spaces.active.region_3d.view_matrix.to_3x3().inverted()
	elif spot_set_space == '4': # Cursor
		spot_orient_matrix = bco.scene.cursor.matrix.to_3x3()
	else: # Preset
		if pr_values != {}:
			euler = mu.Euler((pr_values.get(sot.loc_rot_presets)[1]),'XYZ')
			spot_orient_matrix = euler.to_matrix()
		else:
			spot_orient_matrix = mu.Matrix.Identity(3)

def vcv(co,v,a,av,avv,avc,adv):
	av = a
	if abs(av - round(avv[v]/avc,4)) <= adv:
		avv,avc = avv+co,avc+1 	 
	else:
		avv,avc = co,1

	return av,avv,avc

def spots_calc(mode,space):

	global spot_sob_matrices_vdata
	global spot_orient_matrix
	global spot_sps_data
	spot_sps_data.clear()

	for data in spot_sob_matrices_vdata:

		obm = data[0]
		orm = data[0].to_3x3() if space == '2' and mode != '2' else spot_orient_matrix

		orme = orm.to_euler()
		orm_unic = True if orm != mu.Matrix.Identity(3) else False
		loc = orm.inverted() @ mu.Vector(data[0].col[3][:3]) if orm_unic else mu.Vector(data[0].col[3][:3])

		vdata = data[1]
		fv = orm.inverted() @ Vector(vdata[0]) if orm_unic else Vector(vdata[0])
		ffv = orm @ fv

		xn,xp,yn,yp,zn,zp = round(fv[0],4),round(fv[0],4),round(fv[1],4),round(fv[1],4),round(fv[2],4),round(fv[2],4)
		xnv,xpv,ynv,ypv,znv,zpv,csm = fv,fv,fv,fv,fv,fv,fv
		xnc = xpc = ync = ypc = znc = zpc = 1

		adx = round(0.0002 + (0.0012 * (abs(orme[1]/3.1416) + abs(orme[2]/3.1416))),4)
		ady = round(0.0002 + (0.0012 * (abs(orme[0]/3.1416) + abs(orme[2]/3.1416))),4)
		adz = round(0.0002 + (0.0012 * (abs(orme[0]/3.1416) + abs(orme[1]/3.1416))),4)

		for vco in vdata[1:]:
			co = orm.inverted() @ Vector(vco) if orm_unic else Vector(vco)
			# x,y,z = round(co[0],4),round(co[1],4),round(co[2],4)
			x,y,z = co[0],co[1],co[2]

			if x >= xp - (adx*abs(xp/1000)) : xp,xpv,xpc = vcv(co,0,x,xp,xpv,xpc,adx)
			if x <= xn + (adx*abs(xn/1000)) : xn,xnv,xnc = vcv(co,0,x,xn,xnv,xnc,adx)
			if y >= yp - (ady*abs(yp/1000)) : yp,ypv,ypc = vcv(co,1,y,yp,ypv,ypc,ady)
			if y <= yn + (ady*abs(yn/1000)) : yn,ynv,ync = vcv(co,1,y,yn,ynv,ync,ady)
			if z >= zp - (adz*abs(zp/1000)) : zp,zpv,zpc = vcv(co,2,z,zp,zpv,zpc,adz)
			if z <= zn + (adz*abs(zn/1000)) : zn,znv,znc = vcv(co,2,z,zn,znv,znc,adz)

			csm = csm + co

		boc = mu.Vector((((xn+xp)/2),((yn+yp)/2),((zn+zp)/2)))
		com = csm/vdata.shape[0]

		if xnc != 1: xnv = xnv/xnc
		if xpc != 1: xpv = xpv/xpc
		if ync != 1: ynv = ynv/ync
		if ypc != 1: ypv = ypv/ypc
		if znc != 1: znv = znv/znc
		if zpc != 1: zpv = zpv/zpc

		sps = {'xn':xn,'xp':xp,'yn':yn,'yp':yp,'zn':zn,'zp':zp,'boc':boc,'com':com,
				'xnv':xnv,'xpv':xpv,'ynv':ynv,'ypv':ypv,'znv':znv,'zpv':zpv,'orm':orm,'loc':loc}

		spot_sps_data.append(sps)

def projection_calc(praxis,prdir,drp_m,drp_sm,drp_off,drp_czpb,drp_czpv):

	global spot_sps_data
	global spot_psp_data
	spot_psp_data.clear()


	mzp = (0,0,0)
	if drp_m == '1' and drp_sm == '2':
		locs = [sps.get('loc') for sps in spot_sps_data]
		mzp = mu.Vector((0,0,0))
		for loc in locs:
			mzp += loc
		mzp = mzp/len(locs)


	for sps in spot_sps_data:

		xp,xn,yp,yn,zp,zn,boc = sps.get('xp'),sps.get('xn'),sps.get('yp'),sps.get('yn'),sps.get('zp'),sps.get('zn'),sps.get('boc')

		xc,yc,zc = boc[0],boc[1],boc[2]

		x = xp if prdir == '1' else xn 
		y = yp if prdir == '1' else yn 
		z = zp if prdir == '1' else zn 

		orm = sps.get('orm')

		czp = drp_czpv 

		if orm != mu.Matrix.Identity(3): 
			czp = orm.inverted() @ czp
		zpoint = czp if drp_czpb else (0,0,0)  

		xd = (zpoint[0] if drp_sm == '1' else mzp[0]) if drp_m == '1' else (x if drp_sm == '1' else xc)
		yd = (zpoint[1] if drp_sm == '1' else mzp[1]) if drp_m == '1' else (y if drp_sm == '1' else yc)
		zd = (zpoint[2] if drp_sm == '1' else mzp[2]) if drp_m == '1' else (z if drp_sm == '1' else zc)

		dtp_a = sps.get('loc')
		offset = drp_off * -1 if prdir == '1' and drp_m == '2' else drp_off

		if praxis == '1':
			dtp_b = mu.Vector((xd+offset,dtp_a[1],dtp_a[2]))
			dtp_c = mu.Vector((xd+offset,yd,dtp_a[2]))
			dtp_d = mu.Vector((xd+offset,yd,zd))
			dtp_e = mu.Vector((xd,yd,zd))

			bom = sps.get('xpv') if prdir == '1' else sps.get('xnv')

			psp =  {'np':mu.Vector((x,yn,zp)),'cp':mu.Vector((x,yc,zp)),'pp':mu.Vector((x,yp,zp)),
					'nc':mu.Vector((x,yn,zc)),'cc':mu.Vector((x,yc,zc)),'pc':mu.Vector((x,yp,zc)),
					'nn':mu.Vector((x,yn,zn)),'cn':mu.Vector((x,yc,zn)),'pn':mu.Vector((x,yp,zn)),
					'dtp_a':dtp_a,'dtp_b':dtp_b,'dtp_c':dtp_c,'dtp_d':dtp_d,'dtp_e':dtp_e,
					'bom':bom,'boc':boc,'com':sps.get('com')}

		elif praxis == '2':
			dtp_b = mu.Vector((dtp_a[0],yd+offset,dtp_a[2]))
			dtp_c = mu.Vector((xd,yd+offset,dtp_a[2]))
			dtp_d = mu.Vector((xd,yd+offset,zd))
			dtp_e = mu.Vector((xd,yd,zd))

			bom = sps.get('ypv') if prdir == '1' else sps.get('ynv')

			psp =  {'np':mu.Vector((xn,y,zp)),'cp':mu.Vector((xc,y,zp)),'pp':mu.Vector((xp,y,zp)),
					'nc':mu.Vector((xn,y,zc)),'cc':mu.Vector((xc,y,zc)),'pc':mu.Vector((xp,y,zc)),
					'nn':mu.Vector((xn,y,zn)),'cn':mu.Vector((xc,y,zn)),'pn':mu.Vector((xp,y,zn)),
					'dtp_a':dtp_a,'dtp_b':dtp_b,'dtp_c':dtp_c,'dtp_d':dtp_d,'dtp_e':dtp_e,
					'bom':bom,'boc':boc,'com':sps.get('com')}
		else:
			dtp_b = mu.Vector((dtp_a[0],dtp_a[1],zd+offset)) 
			dtp_c = mu.Vector((dtp_a[0],yd,zd+offset))# if dtp_a[0] >= dtp_a[1] else mu.Vector((xd,dtp_a[1],zd+drp_off))
			dtp_d = mu.Vector((xd,yd,zd+offset))
			dtp_e = mu.Vector((xd,yd,zd))

			bom = sps.get('zpv') if prdir == '1' else sps.get('znv')

			psp =  {'np':mu.Vector((xn,yp,z)),'cp':mu.Vector((xc,yp,z)),'pp':mu.Vector((xp,yp,z)),
					'nc':mu.Vector((xn,yc,z)),'cc':mu.Vector((xc,yc,z)),'pc':mu.Vector((xp,yc,z)),
					'nn':mu.Vector((xn,yn,z)),'cn':mu.Vector((xc,yn,z)),'pn':mu.Vector((xp,yn,z)),
					'dtp_a':dtp_a,'dtp_b':dtp_b,'dtp_c':dtp_c,'dtp_d':dtp_d,'dtp_e':dtp_e,
					'bom':bom,'boc':boc,'com':sps.get('com')}

		axis = {
			'xap':mu.Vector((1,0,0)),'xan':mu.Vector((-1,0,0)),
			'yap':mu.Vector((0,1,0)),'yan':mu.Vector((0,-1,0)),
			'zap':mu.Vector((0,0,1)),'zan':mu.Vector((0,0,-1))}

		bound = {
			'ba':mu.Vector((xp,yn,zp)),'bb':mu.Vector((xp,yp,zp)),'bc':mu.Vector((xp,yp,zn)),'bd':mu.Vector((xp,yn,zn)),
			'be':mu.Vector((xn,yn,zp)),'bf':mu.Vector((xn,yp,zp)),'bg':mu.Vector((xn,yp,zn)),'bh':mu.Vector((xn,yn,zn))}

		psp = {**psp, **axis, **bound}

		if orm != mu.Matrix.Identity(3):
			for k,v in psp.items(): psp[k] = orm @ v

		matrix = {'orm':sps.get('orm')}
		psp = {**psp, **matrix}

		spot_psp_data.append(psp)

def draw_this(shader,coordinates,colors,line_wifdth=1):
	batch = batch_for_shader(shader, 'LINES', {"pos": coordinates, "color": colors})
	bgl.glLineWidth(line_wifdth)
	shader.bind()
	batch.draw(shader)
	bgl.glLineWidth(1)

def color_lerp(ca,cb,n,t):
	if n == 0:
		return mu.Vector(cb)
	else:
		frac = (mu.Vector(cb) - mu.Vector(ca))/t
		return mu.Vector(cb) - (frac*n)  

def color_fade(color,n,t):
	n += 1
	a,b,c,d = color[0],color[1],color[2],color[3]
	af,bf,cf,df = (a/2)/t,(b/2)/t,(c/2)/t,(d/2)/t
	return (a-(af*n),b-(bf*n),c-(cf*n),d-(df*n))

def draw_spots_main(self,context):
	bco = bpy.context
	sot = context.scene.sot_props
	bcv = bco.view_layer
	aob = bco.active_object
	sob = bco.selected_objects

	global spot_mode_space_check
	global spot_projection_check
	global spot_sob_matrices_vdata
	global spot_orient_matrix
	global spot_sps_data
	global spot_psp_data
	global shapes
	global colors

	mode_or_space_recalc = False
	projection_recalc = False

	mode_space = (sot.spot_set_mode,sot.spot_set_space)
	if spot_mode_space_check != mode_space:
		spot_mode_space_check = mode_space
		mode_or_space_recalc = True

	projection_prms = (sot.spot_set_axis,sot.spot_set_dir,sot.drop_to_mode,sot.drop_to_smode,sot.drop_to_offset,sot.drop_custom_zero,sot.czp_x,sot.czp_y,sot.czp_z)
	if spot_projection_check != projection_prms:
		spot_projection_check = projection_prms
		projection_recalc = True

	if sot.draw_spots_recalc or mode_or_space_recalc:
		matrices_vdata_get(sot.spot_set_mode,aob,sob)
		rotation_matrix_get(sot.spot_set_space,bco,sot,aob,sob)
		spots_calc(sot.spot_set_mode,sot.spot_set_space)
		projection_recalc = True

	if projection_recalc:
		projection_calc(sot.spot_set_axis,sot.spot_set_dir,sot.drop_to_mode,sot.drop_to_smode, \
			sot.drop_to_offset,sot.drop_custom_zero,mu.Vector((sot.czp_x,sot.czp_y,sot.czp_z)))

	sot.draw_spots_recalc = False


	s3d = bco.space_data.region_3d
	a3d = bco.area.spaces.active.region_3d
	vmt = a3d.view_matrix.to_3x3()
	ortho_view = True if s3d.view_perspective == 'ORTHO' else False
	if ortho_view: vivec = vmt.inverted() @ mu.Vector((0,0,1))
	else: vivec = vmt.inverted() @ (mu.Vector(a3d.view_matrix.col[3][:3]) * -1)

	gfv = []
	zpv = []

	if sot.spot_set_axis == '1': axicol = [colors[4],colors[5],colors[6]]
	elif sot.spot_set_axis == '2': axicol = [colors[5],colors[4],colors[6]]
	else: axicol = [colors[6],colors[4],colors[5]]

	csd = {'np':(axicol[2],2.2,shapes[3]),   'cp':(colors[0],1,shapes[2]),    'pp':(colors[0],1,shapes[2]),
		   'nc':(axicol[2],2.2,shapes[1]),   'cc':(colors[0],1,shapes[2]),    'pc':(colors[0],1,shapes[2]),
		   'nn':(axicol[0],2.2,shapes[1]),   'cn':(axicol[1],2.2,shapes[1]),  'pn':(axicol[1],2.2,shapes[1]),
		  'bom':(colors[1],2,shapes[2]),    'boc':(colors[2],3.5,shapes[2]), 'com':(colors[3],2.7,shapes[2]),
		'dtp_b':(colors[9],2,shapes[0])}


	shader = gpu.shader.from_builtin('3D_SMOOTH_COLOR')
	spot_psp_data = sorted(spot_psp_data, key=lambda e: (vmt @ e.get('boc'))[2])

	for prd in spot_psp_data:

		if sot.draw_opt_bndc:

			ba,bb,bc,bd,be,bf,bg,bh = prd.get('ba'),prd.get('bb'),prd.get('bc'),prd.get('bd'),prd.get('be'),prd.get('bf'),prd.get('bg'),prd.get('bh')
			xap,xan,yap,yan,zap,zan = prd.get('xap').freeze(),prd.get('xan').freeze(),prd.get('yap').freeze(),prd.get('yan').freeze(),prd.get('zap').freeze(),prd.get('zan').freeze()

			bound = {
			xap:[ba,bb,bb,bc,bc,bd,bd,ba],xan:[be,bf,bf,bg,bg,bh,bh,be],
			yap:[bf,bb,bb,bc,bc,bg,bg,bf],yan:[be,ba,ba,bd,bd,bh,bh,be],
			zap:[bf,bb,bb,ba,ba,be,be,bf],zan:[bg,bc,bc,bd,bd,bh,bh,bg]}

			bound_rrd, bback_crd, bback_col, bfront_crd, bfront_col = [],[],[],[],[]

			for avec,coords in bound.items():
				if (ortho_view and avec.dot(vivec) <= 0) or ( not ortho_view and avec.dot(vivec - prd.get('boc')) <= 0):
					for crd in coords:
						bback_crd.append(crd)
						bback_col.append(colors[8])
						bound_rrd.append(avec)

			for avec,coords in bound.items():
				if not avec in bound_rrd:
					for crd in coords:
						bfront_crd.append(crd)
						bfront_col.append(colors[7])

			draw_this(shader,bback_crd,bback_col,2)
			draw_this(shader,bfront_crd,bfront_col,3)

		if sot.draw_opt_dtpl:
		
			drop_crd = [
				prd.get('dtp_a'),prd.get('dtp_b'),
				prd.get('dtp_b'),prd.get('dtp_c'),
				prd.get('dtp_c'),prd.get('dtp_d'),
				prd.get('dtp_d'),prd.get('dtp_e')] \
				if sot.drop_to_mode == '1' else [
				prd.get('dtp_a'),prd.get('dtp_b')]

			drop_col = [
				colors[10],colors[10],
				colors[11],colors[11],
				colors[11],colors[11],
				colors[11],colors[11],]	\
				if sot.drop_to_mode == '1' else [		
				colors[10],colors[10]]

			draw_this(shader,drop_crd,drop_col,2)

			zero_crd,zero_col = [],[]
			scl = screen_size(bco,prd.get('dtp_e'),True) * csd.get('dtp_b')[1] * sot.draw_spots_scale
			for val in shapes[4]:
					val = (vmt.inverted() @ (mu.Vector(val)*scl)) + prd.get('dtp_e')	
					zero_crd.append(val)
					zero_col.append(csd.get('dtp_b')[0])
			draw_this(shader,zero_crd,zero_col,6)				


			if not sot.draw_opt_bnds:
				dtp_crd, dtp_col = [],[]
				scl = screen_size(bco,prd.get('dtp_b'),True) * csd.get('dtp_b')[1] * sot.draw_spots_scale
				for val in csd.get('dtp_b')[2]:
					val = (vmt.inverted() @ (mu.Vector(val)*scl)) + prd.get('dtp_b')	
					dtp_crd.append(val)
					dtp_col.append(csd.get('dtp_b')[0])
				draw_this(shader,dtp_crd,dtp_col,6)


		if sot.draw_opt_bnds:

			spots = [('np',prd.get('np')),('cp',prd.get('cp')),('pp',prd.get('pp')),
					('nc',prd.get('nc')),('cc',prd.get('cc')),('pc',prd.get('pc')),
					('nn',prd.get('nn')),('cn',prd.get('cn')),('pn',prd.get('pn')),	
					('bom',prd.get('bom')),('boc',prd.get('boc')),('com',prd.get('com')),('dtp_b',prd.get('dtp_b'))]

			spots = sorted(spots, key=lambda e: (vmt @ e[1])[2])

			spots_crd, spots_col = [],[]
			for spt,coords in spots:
				if not sot.draw_opt_dtpl and spt == 'dtp_b':
					continue
				scl = screen_size(bco,coords,True) * csd.get(spt)[1] * sot.draw_spots_scale
				for val in csd.get(spt)[2]:
					val = (vmt.inverted() @ (mu.Vector(val)*scl)) + coords	
					spots_crd.append(val)
					spots_col.append(csd.get(spt)[0])

			draw_this(shader,spots_crd,spots_col,6)
	return

def enum_updateloc_rot_presets(self, context):
	sot = context.scene.sot_props

	pr_enum = []
	pr_num = len(pr_values)
	for k,v in pr_values.items():
		n = len(pr_enum)
		new_pr = (k, k, 'Location = ' + str(v[0]) + ' | Orientation = ' 
			+ str((round(math.degrees(v[1][0]),4),round(math.degrees(v[1][1]),4),round(math.degrees(v[1][2]),4))), n)
		pr_enum.append(new_pr)
	return pr_enum

def prop_update_draw_loc_rot_axis(self, context):
	if context.scene.sot_props.draw_loc_rot_axis:
		bpy.ops.fgt.sot_draw_loc_rot_axis('INVOKE_DEFAULT')
	return

def prop_update_draw_loc_rot_presets(self, context):
	if context.scene.sot_props.draw_loc_rot_presets:
		bpy.ops.fgt.sot_draw_loc_rot_presets('INVOKE_DEFAULT')
	return

def prop_update_loc_mode(self, context):
	sot = context.scene.sot_props
	global loc_mode_current	

	if loc_mode_current != sot.loc_mode:
		loc_mode_current = sot.loc_mode
		if sot.loc_mode == '2':
			bpy.ops.fgt.sot_convert_local('EXEC_DEFAULT')
	return

def prop_update_loc_ltr(self, context):
	sot = context.scene.sot_props

	bpy.ops.fgt.sot_convert_from_local('EXEC_DEFAULT')
	return

def prop_update_rot(self, context):
	sot = context.scene.sot_props
	global rot_update

	if sot.loc_mode == '2':
		rot_update = 3
		bpy.ops.fgt.sot_convert_local('EXEC_DEFAULT')
	return

def prop_update_spot_set_pick(self, context):
	sot =  context.scene.sot_props
	if sot.spot_set_pick == '2' and (sot.spot_set_mode == '3' or sot.spot_set_mode == '4'):
		if sot.spot_set_mode == '4': sot.spot_set_mode = '2'
		elif sot.spot_set_mode == '3': sot.spot_set_mode = '1'
	return

def prop_update_draw_spots(self, context):
	sot =  context.scene.sot_props
	if sot.draw_spots:
		sot.draw_spots_recalc = True
		bpy.ops.fgt.sot_draw_spots('INVOKE_DEFAULT')
	return

def prop_update_draw_spots_recalc(self,context):
	sot =  context.scene.sot_props
	if not sot.draw_spots and sot.draw_spots_recalc:
		sot.draw_spots_recalc = False
	return

def spt_prms(sot,spt_name,drop = False):
	if drop: return sot.spot_set_mode, sot.spot_set_not_active, sot.spot_set_axis, sot.spot_set_dir, sot.spot_set_space, spt_name, \
		sot.drop_to_mode, sot.drop_to_smode, sot.drop_to_offset, sot.drop_custom_zero, mu.Vector((sot.czp_x,sot.czp_y,sot.czp_z))
	else:    return sot.spot_set_mode, sot.spot_set_not_active, sot.spot_set_axis, sot.spot_set_dir, sot.spot_set_space, spt_name




# UI PANEL -------------------------------------------------------------------------------------





class SOT_PT_Panel(bpy.types.Panel):
	bl_label = 'SOT'
	bl_idname = 'SOT_PT_Panel'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'

	def draw(self, context):
		layout = self.layout

class SOT_PT_Location_Orientation(bpy.types.Panel):
	bl_label = 'Location & Orientation'
	bl_idname = 'SOT_PT_Location_Orientation'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_parent_id = 'SOT_PT_Panel'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		sot = context.scene.sot_props
		sts = context.scene.tool_settings
		get = 'fgt.sot_get_transform'

		layout = self.layout
		col = layout.column(align=True)

		if context.mode == 'OBJECT':
			col.prop(sts, 'use_transform_data_origin', icon= 'TRANSFORM_ORIGINS', text= 'Manual Origin Transform', toggle= True)
		col.separator(factor=1)

		row = col.row(align=True)
		row.operator(get, icon='PIVOT_CURSOR', text='Get Cursor')							.prm_get_transform = 'lr_c'
		row.operator(get, icon='ORIENTATION_LOCAL', text='Get Active')						.prm_get_transform = 'lr_a'

		row = col.row(align=True)
		row.label(text= 'Set Origin:')
		if pr_values != {}: row.prop(sot, 'loc_rot_from_preset', text= 'From Preset', icon='PASTEFLIPDOWN', toggle= True)

		prval = True if sot.loc_rot_from_preset and pr_values != {} else False

		row = col.row(align=True)
		set_loc = row.operator('fgt.sot_set_origin_loc_rot', icon='ORIENTATION_GLOBAL', text='Location')
		set_loc.prm_set_loc_rot = 'Loc'
		set_loc.prm_set_act_bat = sot.loc_rot_active_batch
		set_loc.prm_set_location = pr_values.get(sot.loc_rot_presets)[0] if prval else  mu.Vector((sot.loc_x,sot.loc_y,sot.loc_z))
		set_loc.prm_set_rotation = pr_values.get(sot.loc_rot_presets)[1] if prval else  mu.Vector((sot.rot_x,sot.rot_y,sot.rot_z))
		set_rot = row.operator('fgt.sot_set_origin_loc_rot', icon='ORIENTATION_GIMBAL', text='Orientation')
		set_rot.prm_set_loc_rot = 'Rot'
		set_rot.prm_set_act_bat = sot.loc_rot_active_batch
		set_rot.prm_set_location = pr_values.get(sot.loc_rot_presets)[0] if prval else  mu.Vector((sot.loc_x,sot.loc_y,sot.loc_z))
		set_rot.prm_set_rotation = pr_values.get(sot.loc_rot_presets)[1] if prval else  mu.Vector((sot.rot_x,sot.rot_y,sot.rot_z))

		set_both = col.operator('fgt.sot_set_origin_loc_rot', icon='ORIENTATION_LOCAL', text='Location + Orientation')
		set_both.prm_set_loc_rot = 'Loc + Rot'
		set_both.prm_set_act_bat = sot.loc_rot_active_batch
		set_both.prm_set_location = pr_values.get(sot.loc_rot_presets)[0] if prval else mu.Vector((sot.loc_x,sot.loc_y,sot.loc_z))
		set_both.prm_set_rotation = pr_values.get(sot.loc_rot_presets)[1] if prval else mu.Vector((sot.rot_x,sot.rot_y,sot.rot_z))
		col.separator(factor=1)

		row = col.row(align=True)
		row.prop_enum(sot, 'loc_rot_active_batch', icon= 'DOT', value= '1')
		row.prop_enum(sot, 'loc_rot_active_batch', icon= 'LIGHTPROBE_GRID', value= '2')
		row = col.row(align=True)
		row.prop(sot, 'draw_loc_rot_axis', text= 'Hide Helper Axis' if sot.draw_loc_rot_axis else 'Show Helper Axis', icon='EMPTY_AXIS', toggle= True)


class SOT_PT_Location(bpy.types.Panel):
	bl_label = 'Location'
	bl_idname = 'SOT_PT_Location'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_parent_id = 'SOT_PT_Location_Orientation'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		sot = context.scene.sot_props
		clear = 'fgt.sot_clear_value'
		get = 'fgt.sot_get_transform'

		layout = self.layout
		col = layout.column(align=True)

		row = col.row(align=True)
		set_loc = row.operator('fgt.sot_set_origin_loc_rot', icon='ORIENTATION_GLOBAL', text='Set Origin Location')
		set_loc.prm_set_loc_rot = 'Loc'
		set_loc.prm_set_act_bat = sot.loc_rot_active_batch
		set_loc.prm_set_location = mu.Vector((sot.loc_x,sot.loc_y,sot.loc_z))
		col.separator(factor=1)

		row = col.row(align=True)
		row.prop_enum(sot, 'loc_mode', icon= 'ORIENTATION_GLOBAL' ,value= '1')
		row.prop_enum(sot, 'loc_mode', icon= 'ORIENTATION_LOCAL' ,value= '2')

		if sot.loc_mode == '1':
			row = col.row(align=True)
			row.prop(sot, 'loc_x', text= 'X')
			row.operator(clear, icon='X' if sot.loc_x != 0 else 'DOT', text='')				.cop = 'loc_x'
			row = col.row(align=True)
			row.prop(sot, 'loc_y', text= 'Y')
			row.operator(clear, icon='X' if sot.loc_y != 0 else 'DOT', text='')				.cop = 'loc_y'
			row = col.row(align=True)
			row.prop(sot, 'loc_z', text= 'Z')
			row.operator(clear, icon='X' if sot.loc_z != 0 else 'DOT', text='')				.cop = 'loc_z'	
		else:
			row = col.row(align=True)
			row.prop(sot, 'loc_x_ltr', text= 'X')
			row.operator(clear, icon='X' if sot.loc_x_ltr != 0 else 'DOT', text='')			.cop = 'loc_x_ltr'
			row = col.row(align=True)
			row.prop(sot, 'loc_y_ltr', text= 'Y')
			row.operator(clear, icon='X' if sot.loc_y_ltr != 0 else 'DOT', text='')			.cop = 'loc_y_ltr'
			row = col.row(align=True)
			row.prop(sot, 'loc_z_ltr', text= 'Z')
			row.operator(clear, icon='X' if sot.loc_z_ltr != 0 else 'DOT', text='')			.cop = 'loc_z_ltr'

		row = col.row(align=True)
		row.operator(get, icon='PIVOT_CURSOR', text='Get Cursor')							.prm_get_transform = 'loc_c'
		row.operator(get, icon='PIVOT_ACTIVE', text='Get Active')							.prm_get_transform = 'loc_a'
		not_zero = True if sot.loc_x != 0 or sot.loc_y != 0 or sot.loc_z != 0 else False
		if sot.loc_mode == '1':
			row.operator(clear, icon='X' if not_zero else 'DOT', text='')					.cop = 'multi loc_x loc_y loc_z'
		else:
			row.operator(clear, icon='X' if not_zero else 'DOT', text='')					.cop = 'multi loc_x_ltr loc_y_ltr loc_z_ltr'


class SOT_PT_Orientation(bpy.types.Panel):
	bl_label = 'Orientation'
	bl_idname = 'SOT_PT_Orientation'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_parent_id = 'SOT_PT_Location_Orientation'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		sot = context.scene.sot_props
		rotate = 'fgt.sot_rotate_ninety'
		clear = 'fgt.sot_clear_value'
		get = 'fgt.sot_get_transform'

		zax_dic = {'z+':'rem_zp','z-':'rem_zn','y+':'rem_yp','y-':'rem_yn','x+':'rem_xp','x-':'rem_xn'}
		rem_dic = {'z+':sot.rem_zp,'z-':sot.rem_zn,'y+':sot.rem_yp,'y-':sot.rem_yn,'x+':sot.rem_xp,'x-':sot.rem_xn}

		layout = self.layout
		col = layout.column(align=True)

		row = col.row(align=True)
		set_rot = row.operator('fgt.sot_set_origin_loc_rot', icon='ORIENTATION_GIMBAL', text='Set Origin Orientation')
		set_rot.prm_set_loc_rot = 'Rot'
		set_rot.prm_set_act_bat = sot.loc_rot_active_batch
		set_rot.prm_set_rotation = mu.Vector((sot.rot_x,sot.rot_y,sot.rot_z))
		col.separator(factor=1)

		row = col.row(align=True)
		row.operator(rotate, icon='LOOP_FORWARDS', text='')									.rop = '-rot_x'
		row.operator(rotate, icon='LOOP_BACK',     text='')									.rop = '+rot_x'
		row.prop(sot, 'rot_x', text= 'X')
		row.operator(clear, icon='X' if sot.rot_x != 0 else 'DOT', text='')					.cop = 'rot_x'
		row = col.row(align=True)
		row.operator(rotate, icon='LOOP_FORWARDS', text='')									.rop = '-rot_y'
		row.operator(rotate, icon='LOOP_BACK',     text='')									.rop = '+rot_y'
		row.prop(sot, 'rot_y', text= 'Y')
		row.operator(clear, icon='X' if sot.rot_y != 0 else 'DOT', text='')					.cop = 'rot_y'
		row = col.row(align=True)
		row.operator(rotate, icon='LOOP_FORWARDS', text='')									.rop = '-rot_z'
		row.operator(rotate, icon='LOOP_BACK',     text='')									.rop = '+rot_z'
		row.prop(sot, 'rot_z', text= 'Z')
		row.operator(clear, icon='X' if sot.rot_z != 0 else 'DOT', text='')					.cop = 'rot_z'

		row = col.row(align=True)
		row.operator(get, icon='PIVOT_CURSOR', text='Get Cursor')							.prm_get_transform = 'rot_c'
		row.operator(get, icon='PIVOT_ACTIVE', text='Get Active')							.prm_get_transform = 'rot_a'
		not_zero = True if sot.rot_x != 0 or sot.rot_y != 0 or sot.rot_z != 0 else False
		row.operator(clear, icon='X' if not_zero else 'DOT', text='')						.cop = 'multi rot_x rot_y rot_z'

		row = col.row(align=True)
		if sot.z_rem:

			#row.label(text= 'Z+ remap to:')
			row.prop(sot, 'z_rem', text= 'Z+ remap to:', toggle= True)
			row.prop(sot, 'z_axis', text= '')
			row.operator(clear, icon='X' if sot.z_axis != 'z+' else 'DOT', text='')				.cop = 'z_axis'
			row = col.row(align=True)
			row.prop(sot, zax_dic.get(sot.z_axis), text= '')
			row.operator(clear, icon='X' if rem_dic.get(sot.z_axis) != '1' else 'DOT', text='').cop = zax_dic.get(sot.z_axis)
		else:
			row.prop(sot, 'z_rem', text= 'Remap Z+ axis', toggle= True)




class SOT_PT_Presets(bpy.types.Panel):
	bl_label = 'Presets'
	bl_idname = 'SOT_PT_Presets'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_parent_id = 'SOT_PT_Panel'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		sot = context.scene.sot_props
		layout = self.layout
		col = layout.column(align=True)

		row = col.row(align=True)
		row.operator('fgt.sot_preset_add', text='Loc/Rot', icon='IMPORT')
		row.operator('fgt.sot_preset_add_cursor', text='Cursor', icon='PIVOT_CURSOR')
		row.operator('fgt.sot_preset_add_active', text='Active', icon='PIVOT_ACTIVE')

		if pr_values != {}:


			row = col.row(align=True)
			row.operator('fgt.sot_preset_get', text='Loc/Rot', icon='EXPORT')							.prm_preset_get = 'both'
			row.operator('fgt.sot_preset_get', text='Loc', icon='EXPORT')						.prm_preset_get = 'loc'
			row.operator('fgt.sot_preset_get', text='Rot', icon='EXPORT')						.prm_preset_get = 'rot'
			col.separator(factor=1)	

			row = col.row(align=True)
			row.prop(sot, 'loc_rot_presets', text = '')
			row.operator('fgt.sot_preset_rem', text='', icon='X' if len(pr_values) != 0 else 'DOT')

			row = col.row(align=True)
			row.operator('fgt.sot_preset_ren', text='Rename', icon='EVENT_R')
			row.operator('fgt.sot_preset_rrd', text='Up', icon='TRIA_UP')							.reorder_up = True
			row.operator('fgt.sot_preset_rrd', text='Down', icon='TRIA_DOWN')						.reorder_up = False	
			col.prop(sot, 'draw_loc_rot_presets', text= 'Hide Preset Visuals' if sot.draw_loc_rot_presets else 'Show Preset Visuals', icon= 'GRID')

			i = sot.loc_rot_presets
			v = pr_values.get(i)
			col.label(text= str(list(pr_values.keys()).index(i)+1) + '/' + str(len(pr_values)) + ' : ' + i)
			col.label(text= 'Loc ( X ' + str(round(v[0][0],5)) + ' | Y ' + str(round(v[0][1],5)) + ' | Z ' + str(round(v[0][2],5)) + ' )' )
			col.label(text= 'Rot ( X ' + str(round(math.degrees(v[1][0]),5)) + ' | Y ' + str(round(math.degrees(v[1][1]),5)) + ' | Z ' + str(round(math.degrees(v[1][2]),5)) + ' )' )


class SOT_PT_Fixed_Snap(bpy.types.Panel):
	bl_label = 'Fixed Spots Snap'
	bl_idname = 'SOT_PT_Fixed_Snap'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_parent_id = 'SOT_PT_Panel'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		sot = context.scene.sot_props
		clear = 'fgt.sot_clear_value'
		get = 'fgt.sot_get_transform'
		set_pick_operator = 'fgt.sot_fixed_snap' if sot.spot_set_pick == '1' else 'fgt.sot_fixed_spot_pick'
		smode = True if sot.spot_set_pick == '1' else False

		layout = self.layout
		col = layout.column(align=True)

		row = col.row(align=True)
		row.prop_enum(sot, 'spot_set_pick', icon='TRANSFORM_ORIGINS', value= '1')
		row.prop_enum(sot, 'spot_set_pick', icon='EXPORT', value= '2')
		row = col.row(align=True)
		row.prop_enum(sot, 'spot_set_mode', icon='DOT', value= '1')
		row.prop_enum(sot, 'spot_set_mode', icon='STICKY_UVS_LOC', value= '2')
		if sot.spot_set_pick == '1':
			row = col.row(align=True)
			row.prop_enum(sot, 'spot_set_mode', icon='PARTICLE_DATA', value= '3')
			row.prop_enum(sot, 'spot_set_mode', icon='STICKY_UVS_DISABLE', value= '4')
			if sot.spot_set_mode == '3' or sot.spot_set_mode == '4':
				 row = col.row(align=True)
				 row.prop(sot, 'spot_set_not_active', text= 'Exclude Active', icon= 'CANCEL', toggle= True)	
		col.separator(factor=1)

		row = col.row(align=True)
		row.prop_enum(sot, 'spot_set_axis', value= '1')
		row.prop_enum(sot, 'spot_set_axis', value= '2')
		row.prop_enum(sot, 'spot_set_axis', value= '3')
		row = col.row(align=True)
		row.prop_enum(sot, 'spot_set_dir', icon='ADD', value= '1')
		row.prop_enum(sot, 'spot_set_dir', icon='REMOVE', value= '2')
		row = col.row(align=True)
		row.prop_enum(sot, 'spot_set_space', icon='ORIENTATION_GLOBAL', value= '1')
		row.prop_enum(sot, 'spot_set_space', icon='ORIENTATION_LOCAL', value= '2')
		row = col.row(align=True)
		row.prop_enum(sot, 'spot_set_space', icon='ORIENTATION_VIEW', value= '3')
		row.prop_enum(sot, 'spot_set_space', icon='ORIENTATION_CURSOR', value= '4')

		preset_mat = 'From ' + sot.loc_rot_presets if pr_values != {} else 'Presets List Empty'
		row = col.row(align=True)
		row.enabled = True if pr_values != {} else False
		row.prop_enum(sot, 'spot_set_space', icon='EMPTY_AXIS', text=preset_mat, value= '5')
		if sot.spot_set_space == '5' and pr_values != {}:
			row = col.row(align=True)
			row.prop(sot, 'loc_rot_presets', text = '')
			row.prop(sot, 'draw_loc_rot_presets', text= '', icon= 'GRID')
		col.separator(factor=1)

		row = col.row(align=True)
		np = row.operator(set_pick_operator, icon='TRIA_UP', text='')
		np.prm_spt_mode, np.prm_not_active, np.prm_spt_axis, np.prm_spt_dir, np.prm_spt_space, np.prm_spt_spot = spt_prms(sot,'np')
		cp = row.operator(set_pick_operator, icon='KEYFRAME', text='')
		cp.prm_spt_mode, cp.prm_not_active, cp.prm_spt_axis, cp.prm_spt_dir, cp.prm_spt_space, cp.prm_spt_spot = spt_prms(sot,'cp')
		pp = row.operator(set_pick_operator, icon='KEYFRAME', text='')
		pp.prm_spt_mode, pp.prm_not_active, pp.prm_spt_axis, pp.prm_spt_dir, pp.prm_spt_space, pp.prm_spt_spot = spt_prms(sot,'pp')
		bom = row.operator(set_pick_operator, icon='KEYTYPE_BREAKDOWN_VEC', text='Border Mesh')
		bom.prm_spt_mode, bom.prm_not_active, bom.prm_spt_axis, bom.prm_spt_dir, bom.prm_spt_space, bom.prm_spt_spot = spt_prms(sot,'bom')

		row = col.row(align=True)
		nc = row.operator(set_pick_operator, icon='HANDLETYPE_VECTOR_VEC', text='')
		nc.prm_spt_mode, nc.prm_not_active, nc.prm_spt_axis, nc.prm_spt_dir, nc.prm_spt_space, nc.prm_spt_spot = spt_prms(sot,'nc')
		cc = row.operator(set_pick_operator, icon='KEYFRAME', text='')
		cc.prm_spt_mode, cc.prm_not_active, cc.prm_spt_axis, cc.prm_spt_dir, cc.prm_spt_space, cc.prm_spt_spot = spt_prms(sot,'cc')
		pc = row.operator(set_pick_operator, icon='KEYFRAME', text='')
		pc.prm_spt_mode, pc.prm_not_active, pc.prm_spt_axis, pc.prm_spt_dir, pc.prm_spt_space, pc.prm_spt_spot = spt_prms(sot,'pc')
		boc = row.operator(set_pick_operator, icon='KEYTYPE_EXTREME_VEC', text='Bound Center')
		boc.prm_spt_mode, boc.prm_not_active, boc.prm_spt_axis, boc.prm_spt_dir, boc.prm_spt_space, boc.prm_spt_spot = spt_prms(sot,'boc')

		row = col.row(align=True)
		nn = row.operator(set_pick_operator, icon='HANDLETYPE_VECTOR_VEC', text='')
		nn.prm_spt_mode, nn.prm_not_active, nn.prm_spt_axis, nn.prm_spt_dir, nn.prm_spt_space, nn.prm_spt_spot = spt_prms(sot,'nn')
		cn = row.operator(set_pick_operator, icon='HANDLETYPE_VECTOR_VEC', text='')
		cn.prm_spt_mode, cn.prm_not_active, cn.prm_spt_axis, cn.prm_spt_dir, cn.prm_spt_space, cn.prm_spt_spot = spt_prms(sot,'cn')
		pn = row.operator(set_pick_operator, icon='HANDLETYPE_VECTOR_VEC', text='')
		pn.prm_spt_mode, pn.prm_not_active, pn.prm_spt_axis, pn.prm_spt_dir, pn.prm_spt_space, pn.prm_spt_spot = spt_prms(sot,'pn')
		com = row.operator(set_pick_operator, icon='KEYTYPE_KEYFRAME_VEC', text='Center Of Mass')
		com.prm_spt_mode, com.prm_not_active, com.prm_spt_axis, com.prm_spt_dir, com.prm_spt_space, com.prm_spt_spot = spt_prms(sot,'com')
		col.separator(factor=1)

		row = col.row(align=True)
		dtp = row.operator(set_pick_operator, icon='TRIA_DOWN_BAR', text='Drop To')
		dtp.prm_spt_mode, dtp.prm_not_active, dtp.prm_spt_axis, dtp.prm_spt_dir, dtp.prm_spt_space, dtp.prm_spt_spot, dtp.prm_drp_m, dtp.prm_drp_sm, \
			dtp.prm_drp_off, dtp.prm_drp_czpb, dtp.prm_drp_czpv = spt_prms(sot,'dtp_b',True)

		row = col.row(align=True)
		row.prop_enum(sot, 'drop_to_mode', icon='SNAP_PERPENDICULAR', value= '1')
		row.prop_enum(sot, 'drop_to_mode', icon='SNAP_FACE_CENTER', value= '2')
		row = col.row(align=True)
		row.prop_enum(sot, 'drop_to_smode', icon='EMPTY_AXIS' if sot.drop_to_mode == '1' else 'MOD_EDGESPLIT', value= '1', text= 'Zero' if sot.drop_to_mode == '1' else 'Side')
		row.prop_enum(sot, 'drop_to_smode', icon='NLA_PUSHDOWN' if sot.drop_to_mode == '1' else 'ALIGN_MIDDLE', value= '2')

		row = col.row(align=True)
		row.prop(sot, 'drop_to_offset', text= 'Offset')
		row.operator(clear, icon='X' if sot.drop_to_offset != 0 else 'DOT', text='')				.cop = 'drop_to_offset'
		if sot.drop_to_mode == '1' and sot.drop_to_smode == '1':
			col.prop(sot, 'drop_custom_zero', text= 'Custom Zero Point', toggle= True)
			if sot.drop_custom_zero:
				row = col.row(align=True)
				row.prop(sot, 'czp_x', text= 'X') 	
				row.operator(clear, icon='X' if sot.czp_x != 0 else 'DOT', text='')					.cop = 'czp_x'
				row = col.row(align=True)
				row.prop(sot, 'czp_y', text= 'Y')
				row.operator(clear, icon='X' if sot.czp_y != 0 else 'DOT', text='')					.cop = 'czp_y'
				row = col.row(align=True)			
				row.prop(sot, 'czp_z', text= 'Z')
				row.operator(clear, icon='X' if sot.czp_z != 0 else 'DOT', text='')					.cop = 'czp_z'
				row = col.row(align=True)
				emb = True if  pr_values != {} else False
				row.operator(get, icon='EMPTY_AXIS', text='Preset', emboss= emb)					.prm_get_transform = 'czp_p'
				row.operator(get, icon='PIVOT_CURSOR', text='Cursor')								.prm_get_transform = 'czp_c'
				row.operator(get, icon='PIVOT_ACTIVE', text='Active')								.prm_get_transform = 'czp_a'
				not_zero = True if sot.czp_x != 0 or sot.czp_y != 0 or sot.czp_z != 0 else False
				row.operator(clear, icon='X' if not_zero else 'DOT', text='')						.cop = 'multi czp_x czp_y czp_z'

		col.separator(factor=1)
		row = col.row(align=True)
		row.prop(sot, 'draw_spots', text= 'Hide Visuals' if sot.draw_spots else 'Show Visuals', 
			icon='RADIOBUT_OFF' if not sot.draw_spots else 'RADIOBUT_ON', toggle= True)
		if sot.draw_spots:
			row.prop(sot, 'draw_spots_recalc', text= 'Refresh', icon='FILE_REFRESH', toggle= True)
		if sot.draw_spots:
			row = col.row(align=True)
			row.prop(sot, 'draw_spots_scale', text= 'Spots Scale')
			row.operator(clear, icon='X' if sot.draw_spots_scale != 1 else 'DOT', text='')			.cop = 'draw_spots_scale'
			row = col.row(align=True)
			row.prop(sot, 'draw_opt_bndc', icon='CUBE', text= 'Cage')
			row.prop(sot, 'draw_opt_bnds', icon='GROUP_VERTEX', text= 'Spots')
			row.prop(sot, 'draw_opt_dtpl', icon='TRACKING_BACKWARDS_SINGLE', text= 'Drop')






# OPERATORS------------------------------------------------------------------------------------------------------






class SOT_OT_Preset_Ren(bpy.types.Operator):
	bl_idname = 'fgt.sot_preset_ren'
	bl_label = 'Rename'
	bl_description = 'Rename selected item (if name is not unique - numbering will be assigned)'

	prm_new_name: bpr.StringProperty(name = '', default= 'New Name')

	def execute(self, context):
		sot = context.scene.sot_props
		new_name = self.prm_new_name
		new_values = {}
		global pr_values

		if new_name == '': return report(self,'Please enter at least something')

		for k,v in pr_values.items():
			if k != sot.loc_rot_presets: 
				new_values[k] = v
			else: 
				new_name = unic_name_geterator(new_name,pr_values.keys(),True,sot.loc_rot_presets)
				new_values[new_name] = v
		pr_values = new_values

		return{'FINISHED'}

	def invoke(self, context, event):
		if pr_values != {}: 
			self.prm_new_name = context.scene.sot_props.loc_rot_presets
			return context.window_manager.invoke_props_dialog(self, width=150)
		else: return report(self,'Presets list is EMPTY!!!')	


class SOT_OT_Preset_Add(bpy.types.Operator):
	bl_idname = 'fgt.sot_preset_add'
	bl_label = 'New Preset'
	bl_description = 'Save current loc/rot values as preset'

	prm_name: bpr.StringProperty(name = '', default= 'Preset')

	def execute(self, context):
		sot = context.scene.sot_props
		name = self.prm_name

		if name == '': return report(self,'Please enter at least something')	

		name = unic_name_geterator(name,pr_values.keys())
		lx,ly,lz,rx,ry,rz = sot.loc_x,sot.loc_y,sot.loc_z, sot.rot_x, sot.rot_y, sot.rot_z
		pr_values[name] = ((round(lx,5),round(ly,5),round(lz,5)),(rx,ry,rz))
		sot.loc_rot_presets = (list(pr_values.keys())[len(pr_values) - 1])

		return{'FINISHED'}

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=150)

class SOT_OT_Preset_Add_Cursor(bpy.types.Operator):
	bl_idname = 'fgt.sot_preset_add_cursor'
	bl_label = 'New Preset From Cursor'
	bl_description = 'Create preset from current 3D Cursor location/rotation'

	def execute(self, context):
		bpy.ops.fgt.sot_get_transform(prm_get_transform= 'loc_c')
		bpy.ops.fgt.sot_get_transform(prm_get_transform= 'rot_c')
		bpy.ops.fgt.sot_preset_add('INVOKE_DEFAULT')

		return{'FINISHED'}


class SOT_OT_Preset_Add_Active(bpy.types.Operator):
	bl_idname = 'fgt.sot_preset_add_active'
	bl_label = 'New Preset From Active'
	bl_description = 'Create preset from current Active object/element location/rotation'

	def execute(self, context):
		sot = context.scene.sot_props

		bpy.ops.fgt.sot_preset_add('INVOKE_DEFAULT')

		return{'FINISHED'}

class SOT_OT_Preset_Rem(bpy.types.Operator):
	bl_idname = 'fgt.sot_preset_rem'
	bl_label = 'Remove'
	bl_description = 'Remove current item from presets list'

	def execute(self, context):
		sot = context.scene.sot_props

		if len(pr_values) != 0:
			if list(pr_values.keys()).index(sot.loc_rot_presets) == len(pr_values) - 1:
				del pr_values[sot.loc_rot_presets]
				if len(pr_values) != 0:
					sot.loc_rot_presets = (list(pr_values.keys())[len(pr_values) - 1])
			else:
				del pr_values[sot.loc_rot_presets]

			if pr_values == {} and sot.spot_set_space == '5': sot.spot_set_space = '1'

		else: return report(self,'No more items to remove')
		return{'FINISHED'}

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=150)	


class SOT_OT_Preset_Rrd(bpy.types.Operator):
	bl_idname = 'fgt.sot_preset_rrd'
	bl_label = 'Reorder'
	bl_description = 'Move current item up/down in presets list (if possible)'

	reorder_up: bpr.BoolProperty()

	def execute(self, context):
		global pr_values
		if pr_values == {}: return report(self,"Presets list is EMPTY!!!")
		sot = context.scene.sot_props
		ind = list(pr_values.keys()).index(sot.loc_rot_presets)
		new_pr,ksi,ks = {},[],[]

		if self.reorder_up :
			if ind != 0:
				ksi = [e for e,i in  enumerate(pr_values.keys())]
				ksi[ind] = ksi[ind]-1
				ksi[ind-1] = ksi[ind]+1
				ks = [list(pr_values.keys())[i] for i in ksi]
				for k in ks: new_pr[k] = pr_values.get(k)
				pr_values = new_pr
				sot.loc_rot_presets = ks[ind-1]
			else: return report(self,"Can't move this item UP!!!")
		else:
			if ind != len(pr_values) - 1:
				ksi = [e for e,i in  enumerate(pr_values.keys())]
				ksi[ind] = ksi[ind]+1
				ksi[ind+1] = ksi[ind]-1
				ks = [list(pr_values.keys())[i] for i in ksi]
				for k in ks: new_pr[k] = pr_values.get(k)
				pr_values = new_pr
				sot.loc_rot_presets = ks[ind+1]
			else: return report(self,"Can't move this item DOWN!!!")
		return{'FINISHED'}


class SOT_OT_Preset_Get(bpy.types.Operator):
	bl_idname = 'fgt.sot_preset_get'
	bl_label = 'Get Values'
	bl_description = 'Get values from preset'

	prm_preset_get: bpr.EnumProperty(items= [('loc','Get Location','',1),('rot','Get Rotation','',2),('both','Get Location And Rotation','',3)])


	def execute(self, context):
		sot = context.scene.sot_props

		if pr_values == {}:
			return report(self,"Presets list is EMPTY!!!")
		else:
			if   self.prm_preset_get == 'loc': sot.loc_x,sot.loc_y,sot.loc_z = pr_values.get(sot.loc_rot_presets)[0] 
			elif self.prm_preset_get == 'rot': sot.rot_x, sot.rot_y, sot.rot_z = pr_values.get(sot.loc_rot_presets)[1]
			else:
				sot.loc_x,sot.loc_y,sot.loc_z = pr_values.get(sot.loc_rot_presets)[0] 
				sot.rot_x, sot.rot_y, sot.rot_z = pr_values.get(sot.loc_rot_presets)[1]	
		return{'FINISHED'}


class SOT_OT_Set_Loc_Rot(bpy.types.Operator):
	bl_idname = 'fgt.sot_set_origin_loc_rot'
	bl_label = 'Set Origin Transforms'
	bl_description = 'Set origin location/orientation'
	bl_options = {'REGISTER', 'UNDO'}

	prm_set_loc_rot:	bpr.EnumProperty(name= 'Set Origin', items= [('Loc','Location','',1),('Rot','Rotation','',2),('Loc + Rot','Location + Rotation','',3)])
	prm_set_act_bat: 	bpr.EnumProperty(name= 'Set Mode', items= [('1','Active','',1),('2','Batch','',2)])
	prm_set_location:	bpr.FloatVectorProperty(name= 'Location', subtype= 'XYZ_LENGTH', unit= 'LENGTH', precision= 6)
	prm_set_rotation:	bpr.FloatVectorProperty(name= 'Rotation', subtype= 'EULER', soft_min= -360.0, soft_max= 360.0)

	def execute(self,context):
		bob = bpy.ops.object
		sot = context.scene.sot_props
		bco = bpy.context
		bcv = bco.view_layer
		aob = bcv.objects.active
		sob = bco.selected_objects
		oob = sob
		aob_r = aob
		sob_r = sob
		loc_rot = self.prm_set_loc_rot

		xl,yl,zl = self.prm_set_location
		xr,yr,zr = self.prm_set_rotation[:]

		eob = object_in_edit(bob,sob_r)

		if self.prm_set_act_bat == '1':
			if aob == None: return report(self,'No ACTIVE object in selection!!!!')
			if loc_rot == 'Loc' or loc_rot == 'Loc + Rot': set_origin_location(xl,yl,zl,aob,bcv)
			if loc_rot == 'Rot' or loc_rot == 'Loc + Rot': set_origin_orientation(xr,yr,zr,aob,bcv,bob)
		else:
			if sob_r == []: return report(self,'No SELECTED objects!!!!')
			for tob in sob_r:
				if loc_rot == 'Loc' or loc_rot == 'Loc + Rot': set_origin_location(xl,yl,zl,tob,bcv,oob)
				if loc_rot == 'Rot' or loc_rot == 'Loc + Rot': set_origin_orientation(xr,yr,zr,tob,bcv,bob)

		recover_edit(eob,bcv,aob_r,sob_r)

		return {'FINISHED'}


class SOT_OT_Get_Transform(bpy.types.Operator):
	bl_idname = 'fgt.sot_get_transform'
	bl_label = 'SOT_OT_Get_Transform'
	bl_description = 'Get transform values from...'

	prm_get_transform:	bpr.EnumProperty(name= 'Get Transform', items= [
		('loc_c','Cursor','',1),('loc_a','Active','',2),
		('rot_c','Cursor','',3),('rot_a','Active','',4),
		('lr_c','Cursor','',5),('lr_a','Active','',6),
		('czp_p','Preset','',7),('czp_c','Cursor','',8),('czp_a','Active','',9)])

	def execute(self,context):
		sot = context.scene.sot_props
		gtr = self.prm_get_transform
		bco = bpy.context
		bcv = bco.view_layer
		aob = bcv.objects.active

		if gtr == 'loc_c':		#Get location from Cursor
			set_manual_values(sot,get_cursor_loc_rot(bco,sot,True),'loc')

		elif gtr == 'loc_a':		#Get location from Active Object/Element
			if bco.mode == 'OBJECT':
				value = get_object_loc_rot(self,bco,sot,True)
				if type(value) is not set: set_manual_values(sot,value,'loc')
			elif bco.mode == 'EDIT_MESH':
				value = get_element_loc(self,bco,sot,aob)
				if type(value) is not set: set_manual_values(sot, value,'loc')

		elif gtr == 'rot_c':		#Get rotation from Cursor
			set_manual_values(sot, get_cursor_loc_rot(bco,sot,False).to_euler(),'rot')

		elif gtr == 'rot_a':		#Get rotation from Active Object/Element
			if bco.mode == 'OBJECT':
				value = get_object_loc_rot(self,bco,sot,False)
				if type(value) is not set: set_manual_values(sot, value.to_euler(),'rot')
			elif bco.mode == 'EDIT_MESH':
				value = get_element_vectors(self,bco,sot,aob)
				if type(value) is not set: set_manual_values(sot, value.to_euler(),'rot')

		elif gtr == 'lr_c':			# Get Loc/Rot from Cursor
			set_manual_values(sot,get_cursor_loc_rot(bco,sot,True),'loc')
			set_manual_values(sot, get_cursor_loc_rot(bco,sot,False).to_euler(),'rot')

		elif gtr == 'lr_a':			# Get Loc/Rot from Active
			if bco.mode == 'OBJECT':
				value = get_object_loc_rot(self,bco,sot,True)
				if type(value) is not set: set_manual_values(sot,value,'loc')
				value = get_object_loc_rot(self,bco,sot,False)
				if type(value) is not set: set_manual_values(sot, value.to_euler(),'rot')

			elif bco.mode == 'EDIT_MESH':
				value = get_element_loc(self,bco,sot,aob)
				if type(value) is not set: set_manual_values(sot, value,'loc')
				value = get_element_vectors(self,bco,sot,aob)
				if type(value) is not set: set_manual_values(sot, value.to_euler(),'rot')

		elif gtr == 'czp_p':		#Get location from Preset
			set_manual_values(sot,get_preset_loc_rot(sot,True),'czp')

		elif gtr == 'czp_c':		#Get location from Cursor
			set_manual_values(sot,get_cursor_loc_rot(bco,sot,True),'czp')

		elif gtr == 'czp_a':		#Get location from Active Object/Element
			if bco.mode == 'OBJECT':
				value = get_object_loc_rot(self,bco,sot,True)
				if type(value) is not set: set_manual_values(sot,value,'czp')
			elif bco.mode == 'EDIT_MESH':
				value = get_element_loc(self,bco,sot,aob)
				if type(value) is not set: set_manual_values(sot, value,'czp')

		return {'FINISHED'}

class SOT_OT_Rotate_Ninety(bpy.types.Operator):
	bl_idname = 'fgt.sot_rotate_ninety'
	bl_label = 'SOT_OT_Rotate_Ninety'
	bl_description = 'Rotate orientation around this axis by 90 degrees'

	rop: bpr.StringProperty(name = '', default = '')

	def execute(self,context):
		sot = context.scene.sot_props

		euler = mu.Euler((sot.rot_x,sot.rot_y,sot.rot_z),'XYZ')
		rmt = euler.to_matrix()
		rop_dic = {'x':rmt.col[0],'y':rmt.col[1],'z':rmt.col[2],'-':-90, '+':90}
		rmt.rotate(mu.Quaternion(rop_dic.get(self.rop[-1]), math.radians(rop_dic.get(self.rop[0]))))
		sot.rot_x,sot.rot_y,sot.rot_z = rmt.to_euler()

		if abs(math.degrees(sot.rot_x)) < 0.0001: sot.rot_x = 0
		if abs(math.degrees(sot.rot_y)) < 0.0001: sot.rot_y = 0
		if abs(math.degrees(sot.rot_z)) < 0.0001: sot.rot_z = 0

		return {'FINISHED'}


class SOT_OT_Fixed_Snap(bpy.types.Operator):
	bl_idname = 'fgt.sot_fixed_snap'
	bl_label = 'Origin Fixed Spot Snap'
	bl_description = 'Snap origin position to fixed bounding box/scene point'
	bl_options = {'REGISTER', 'UNDO'}

	prm_spt_mode: bpr.EnumProperty(name= 'Fixed Spot Mode', items= [('1','Active','',1),('2','Multi','',2),('3','To Active','',3),('4','For Each','',4)])
	prm_not_active: bpr.BoolProperty(name= 'Exclude Active', default= False, description= 'Only for To Active and For Each modes, leave Active object unchanged')
	prm_spt_axis: bpr.EnumProperty(name= 'Proojection Along', items= [('1','X Axis','',1),('2','Y Axis','',2),('3','Z Axis','',3)])
	prm_spt_dir: bpr.EnumProperty(name= 'Projection Direction', items= [('1','Positive','',1),('2','Negative','',2)])
	prm_spt_space: bpr.EnumProperty(name = 'Projection Space', items= [('1','Global','',1),('2','Local','',2),('3','View','',3),('4','Cursor','',4),('5','Preset','',5)])
	prm_spt_spot: bpr.EnumProperty(name='Choose Spot',
		items= [
		('np','Projection A Neg - B Pos','',1),
		('cp','Projection A Cen - B Pos','',2),
		('pp','Projection A Pos - B Pos','',3),
		('nc','Projection A Neg - B Cen','',4),
		('cc','Projection A Cen - B Cen','',5),
		('pc','Projection A Pos - B Cen','',6),
		('nn','Projection A Neg - B Neg','',7),
		('cn','Projection A Cen - B Neg','',8),
		('pn','Projection A Pos - B Neg','',9),
		('bom','Border Nesh Spot','',10),
		('boc','Bound Center Spot','',11),
		('com','Center Of Mass Spot','',12),
		('dtp_b','Drop To Spot','',13)])
	prm_drp_m: bpr.EnumProperty(name= 'Drop To Mode', items= [('1','Space','',1),('2','Bound','',2)])
	prm_drp_sm: bpr.EnumProperty(name= 'Drop To Submode', items= [('1','Zero','',1),('2','Median','',2)])
	prm_drp_off: bpr.FloatProperty(name= 'Drop To Offset', subtype = 'DISTANCE', precision= 6)
	prm_drp_czpb: bpr.BoolProperty(name= 'Use Custom Zero', default= False, description= 'Only for Drop To Mode = Space + Drop To Submode = Zero')
	prm_drp_czpv: bpr.FloatVectorProperty( name= 'Custom Zero', subtype= 'XYZ_LENGTH', unit= 'LENGTH', precision= 6)

	def execute(self,context):
		bob = bpy.ops.object
		bco = bpy.context
		bcv = bco.view_layer
		sot = context.scene.sot_props
		aob = bco.active_object
		sob = bco.selected_objects


		if not 'MESH' in [ob.type for ob in sob]: return report(self,'No MESH objects in selection!!!')
		if self.prm_spt_mode == '1' or self.prm_spt_mode == '3':
			if aob_check(aob)[0]:  return report(self, aob_check(aob)[1])		
			elif aob.type != 'MESH': return report(self,'ACTIVE object is not MESH type!!!')

		mob = [ob for ob in sob if ob.type == 'MESH']
		aob_r = aob
		sob_r = sob


		global spot_sob_matrices_vdata
		global spot_orient_matrix
		global spot_psp_data

		if pr_values == {} and sot.spot_set_space == '5': 
			sot.spot_set_space = '1'
			self.prm_spt_space = '1'

		matrices_vdata_get(self.prm_spt_mode,aob,sob)
		rotation_matrix_get(self.prm_spt_space,bco,sot,aob,sob)
		spots_calc(self.prm_spt_mode,self.prm_spt_space)
		projection_calc(self.prm_spt_axis,self.prm_spt_dir,self.prm_drp_m,self.prm_drp_sm, \
						self.prm_drp_off,self.prm_drp_czpb,self.prm_drp_czpv)

		xl,yl,zl = spot_psp_data[0].get(self.prm_spt_spot)

		eob = object_in_edit(bob,sob_r)

		if self.prm_spt_mode == '1':
			set_origin_location(xl,yl,zl,aob,bcv)
		elif self.prm_spt_mode == '2':
			for tob in mob:
				set_origin_location(xl,yl,zl,tob,bcv)
		elif self.prm_spt_mode == '3':
			for tob in sob_r:
				if self.prm_not_active and tob == aob: continue
				set_origin_location(xl,yl,zl,tob,bcv)
		else:
			for index,tob in enumerate(mob):
				if self.prm_not_active and tob == aob: continue
				xl,yl,zl = spot_psp_data[index].get(self.prm_spt_spot)
				set_origin_location(xl,yl,zl,tob,bcv)

		recover_edit(eob,bcv,aob_r,sob_r)


		# bob = bpy.ops.object
		# spot = self.prm_set_spot_d
		# rep = self.report
		# sot = context.scene.sot_props
		# bco = bpy.context
		# bcv = bco.view_layer
		# aob = bcv.objects.active
		# sob = bco.selected_objects
		# aob_r = aob
		# sob_r = sob

		# if sot.spot_set_pick == '2':
		# 	if aob_check(aob)[0]: return report(self, aob_check(aob)[1])

		# 	psp = get_snap_spot_active(bco,sot,aob)
		# 	sot.loc_x,sot.loc_y,sot.loc_z = psp.get(spot)
		# 	bpy.ops.ed.undo_push(message = 'Pick Spot Location' )

		# else:
		# 	if sot.spot_set_mode == '1' or sot.REPLACE_ME_PLEASE == '1':

		# 		if aob_check(aob)[0]:  return report(self, aob_check(aob)[1])
		# 		if mesh_check(aob)[0]: return report(self, mesh_check(aob)[1])

		# 		psp = get_snap_spot_active(bco,sot,aob)
		# 		x,y,z = psp.get(spot)


		# 		'''
		# 		NOTE
		# 		анду пуш, покищо хай полежить
		# 		'''

		# 		eob = object_in_edit(bob,sob_r)
		# 		if sot.spot_set_mode == '1':
		# 			set_origin_location(x,y,z,aob,bcv)
		# 			#bpy.ops.ed.undo_push(message = 'SOT Fixed Snap A')
		# 		elif sot.spot_set_mode == '2':
		# 			for tob in sob:
		# 				if sot.spot_set_not_active:
		# 					if tob == aob_r:
		# 						continue
		# 				set_origin_location(x,y,z,tob,bcv)
		# 			#bpy.ops.ed.undo_push(message = 'SOT Fixed Snap BTA')
		# 		recover_edit(eob,bcv,aob_r,sob_r)

		# 	if sot.spot_set_mode == '2':

		# 		if aob_check(aob)[0]:  return report(self, aob_check(aob)[1])
		# 		for tob in sob:
		# 			if mesh_check(tob)[0]:return report(self, mesh_check(tob)[1])

		# 		eob = object_in_edit(bob,sob_r)
		# 		bpy.ops.ed.undo_push(message = 'SOT Fixed Snap M' )
		# 		recover_edit(eob,bcv,aob_r,sob_r)

		# 	if sot.spot_set_mode == '3' and sot.REPLACE_ME_PLEASE == '2':

		# 		for tob in sob:
		# 			if mesh_check(tob)[0]:return report(self, mesh_check(tob)[1])

		# 		eob = object_in_edit(bob,sob_r)
		# 		for tob in sob:
		# 			vdt = tob.data.vertices
		# 			obm = tob.matrix_world
		# 			sps = spots(sot,obm,vdt)
		# 			psp = projection(sot,obm,sps)[0]
		# 			psp['dtp'] = projection(sot,obm,sps)[2][1]
		# 			x,y,z = psp.get(spot)
		# 			set_origin_location(x,y,z,tob,bcv)
		# 		bpy.ops.ed.undo_push(message = 'SOT Fixed Snap BPO' )
		# 		recover_edit(eob,bcv,aob_r,sob_r)

		return{'FINISHED'}


class SOT_OT_Fixed_Spot_Pick(bpy.types.Operator):
	bl_idname = 'fgt.sot_fixed_spot_pick'
	bl_label = 'Fixed Spot Pick Location'
	bl_description = 'Pick location of projection spot'

	prm_spt_mode: bpr.EnumProperty(name= 'Fixed Spot Mode', items= [('1','Active','',1),('2','Multi','',2)])
	prm_spt_axis: bpr.EnumProperty(name= 'Proojection Along', items= [('1','X Axis','',1),('2','Y Axis','',2),('3','Z Axis','',3)])
	prm_spt_dir: bpr.EnumProperty(name= 'Projection Direction', items= [('1','Positive','',1),('2','Negative','',2)])
	prm_spt_space: bpr.EnumProperty(name = 'Projection Space', items= [('1','Global','',1),('2','Local','',2),('3','View','',3),('4','Cursor','',4),('5','Preset','',5)])
	prm_spt_spot: bpr.EnumProperty(name='Choose Spot',
		items= [
		('np','Projection A Neg - B Pos','',1),
		('cp','Projection A Cen - B Pos','',2),
		('pp','Projection A Pos - B Pos','',3),
		('nc','Projection A Neg - B Cen','',4),
		('cc','Projection A Cen - B Cen','',5),
		('pc','Projection A Pos - B Cen','',6),
		('nn','Projection A Neg - B Neg','',7),
		('cn','Projection A Cen - B Neg','',8),
		('pn','Projection A Pos - B Neg','',9),
		('bom','Border Nesh Spot','',10),
		('boc','Bound Center Spot','',11),
		('com','Center Of Mass Spot','',12),
		('dtp_b','Drop To Spot','',13)])
	prm_drp_m: bpr.EnumProperty(name= 'Drop To Mode', items= [('1','Space','',1),('2','Bound','',2)])
	prm_drp_sm: bpr.EnumProperty(name= 'Drop To Submode', items= [('1','Zero','',1),('2','Median','',2)])
	prm_drp_off: bpr.FloatProperty(name= 'Drop To Offset', subtype = 'DISTANCE', precision= 6)
	prm_drp_czpb: bpr.BoolProperty(name= 'Use Custom Zero', default= False, description= 'Only for Drop To Mode = Space + Drop To Submode = Zero')
	prm_drp_czpv: bpr.FloatVectorProperty( name= 'Custom Zero', subtype= 'XYZ_LENGTH', unit= 'LENGTH', precision= 6)

	def execute(self,context):
		bco = bpy.context
		sot = context.scene.sot_props
		aob = bco.active_object
		sob = bco.selected_objects

		if not 'MESH' in [ob.type for ob in sob]: return report(self,'No MESH objects in selection!!!')
		if self.prm_spt_mode == '1':	
			if aob_check(aob)[0]:  return report(self, aob_check(aob)[1])
			elif aob.type != 'MESH': return report(self,'ACTIVE object is not MESH type!!!')

		global spot_sob_matrices_vdata
		global spot_orient_matrix
		global spot_psp_data

		if pr_values == {} and sot.spot_set_space == '5': 
			sot.spot_set_space = '1'

		print('\nPICK SPOT ------------------------------')

		matrices_vdata_get(self.prm_spt_mode,aob,sob)
		rotation_matrix_get(self.prm_spt_space,bco,sot,aob,sob)
		spots_calc(self.prm_spt_mode,self.prm_spt_space)
		projection_calc(self.prm_spt_axis,self.prm_spt_dir,self.prm_drp_m,self.prm_drp_sm, \
						self.prm_drp_off,self.prm_drp_czpb,self.prm_drp_czpv)

		sot.loc_x,sot.loc_y,sot.loc_z = spot_psp_data[0].get(self.prm_spt_spot)

		return{'FINISHED'}

class SOT_OT_Convert_Local(bpy.types.Operator):
	bl_idname = 'fgt.sot_convert_local'
	bl_label = 'SOT_OT_Clear_Value'

	def execute(self,context):
		sot = context.scene.sot_props

		rot_mat = mu.Euler((sot.rot_x,sot.rot_y,sot.rot_z), 'XYZ').to_matrix()
		ltr = rot_mat.inverted() @ mu.Vector((sot.loc_x,sot.loc_y,sot.loc_z))

		sot.loc_x_ltr = ltr[0]
		sot.loc_y_ltr = ltr[1]
		sot.loc_z_ltr = ltr[2]

		return {'FINISHED'}


class SOT_OT_Convert_From_Local(bpy.types.Operator):
	bl_idname = 'fgt.sot_convert_from_local'
	bl_label = 'SOT_OT_Clear_Value'

	def execute(self,context):
		sot = context.scene.sot_props
		global rot_update

		if rot_update != 0:
			rot_update -= 1

		else:
			rot_mat = mu.Euler((sot.rot_x,sot.rot_y,sot.rot_z), 'XYZ').to_matrix()
			gtr = rot_mat @ mu.Vector((sot.loc_x_ltr,sot.loc_y_ltr,sot.loc_z_ltr))

			sot.loc_x = gtr[0]
			sot.loc_y = gtr[1]
			sot.loc_z = gtr[2]

		return {'FINISHED'}


class SOT_OT_Clear_Value(bpy.types.Operator):
	bl_idname = 'fgt.sot_clear_value'
	bl_label = 'SOT_OT_Clear_Value'

	cop: bpr.StringProperty(name = '', default = '')
	cln_dic = {'loc_x':'= 0','loc_y':'= 0','loc_z':'= 0',
				'loc_x_ltr':'= 0','loc_y_ltr':'= 0','loc_z_ltr':'= 0',
				'rot_x':'= 0','rot_y':'= 0','rot_z':'= 0',
				'z_axis':"= 'z+'",'rem_zp':"= '1'",'rem_zn':"= '1'",
				'rem_yp':"= '1'",'rem_yn':"= '1'",'rem_xp':"= '1'",'rem_xn':"= '1'",
				'drop_to_offset':'= 0', 'czp_x':'= 0', 'czp_y':'= 0', 'czp_z':'= 0',
				'draw_spots_scale':'= 1'}

	def execute(self,context):
		sot = context.scene.sot_props
		if 'multi' in self.cop:
			for prm in self.cop.split()[1:]:
				exec('sot.'+ prm + self.cln_dic.get(prm))
			bpy.ops.ed.undo_push(message = 'SOT Clear Value' )
		else:
			exec('sot.'+ self.cop + self.cln_dic.get(self.cop))
			bpy.ops.ed.undo_push(message = 'SOT Clear Value' )
		return {'FINISHED'}


class SOT_OT_Draw_Axis(bpy.types.Operator):
	bl_idname = 'fgt.sot_draw_loc_rot_axis'
	bl_label = 'SOT_OT_Draw_Axis'

	def stop(self):
		bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
		return {'CANCELLED'}

	def modal(self,context,event):

		sot = context.scene.sot_props
	
		if not sot.draw_loc_rot_axis:
			return self.stop()

		try:
			context.area.tag_redraw()
		except:
			sot.draw_loc_rot_axis = False
			return self.stop()

		else:
			context.area.tag_redraw()
			return {'PASS_THROUGH'}

	def invoke(self,context,event):
		for area in bpy.context.window.screen.areas:
			if area.type == 'VIEW_3D':
				args = (self,context)
				self.draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_loc_rot_axis_main, args, 'WINDOW', 'POST_VIEW')
				context.window_manager.modal_handler_add(self)
				return {'RUNNING_MODAL'}


class SOT_OT_Draw_Presets(bpy.types.Operator):
	bl_idname = 'fgt.sot_draw_loc_rot_presets'
	bl_label = 'SOT_OT_Draw_Axis'

	def modal(self,context,event):

		sot = context.scene.sot_props

		if not sot.draw_loc_rot_presets:
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
			return {'CANCELLED'}

		try:
			context.area.tag_redraw()
		except:
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
			sot.draw_loc_rot_presets = False
			return {'CANCELLED'}
		else:
			context.area.tag_redraw()
			return {'PASS_THROUGH'}

	def invoke(self,context,event):
		for area in bpy.context.window.screen.areas:
			if area.type == 'VIEW_3D':
				args = (self,context)
				self.draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_loc_rot_presets_main, args, 'WINDOW', 'POST_VIEW')
				context.window_manager.modal_handler_add(self)
				return {'RUNNING_MODAL'}


class SOT_OT_Draw_Spots(bpy.types.Operator):
	bl_idname = 'fgt.sot_draw_spots'
	bl_label = 'SOT_OT_Draw_Spots'

	def modal(self,context,event):
		sot = context.scene.sot_props
	
		if not sot.draw_spots:
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
			sot.draw_spots_recalc = False
			return {'CANCELLED'}

		try:
			context.area.tag_redraw()
		except:
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
			sot.draw_spots_recalc = False
			sot.draw_spots = False
			return {'CANCELLED'}
		else:
			context.area.tag_redraw()
			return {'PASS_THROUGH'}

	def invoke(self,context,event):
		for area in bpy.context.window.screen.areas:
			if area.type == 'VIEW_3D':
				args = (self,context)
				self.draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_spots_main, args, 'WINDOW', 'POST_VIEW')
				context.window_manager.modal_handler_add(self)
				return {'RUNNING_MODAL'}




# PROPPERTIES -----------------------------------------------------





class SOT_PR_Settings_Props(bpy.types.PropertyGroup):

	loc_rot_from_preset: bpr.BoolProperty(name = '', default = False)
	loc_rot_active_batch: bpr.EnumProperty(
		items= [('1','Active','Set ORIGIN for ACTIVE object only',1),
				('2','Batch','Set ORIGIN for EACH object in selection',2)], default= '1')
	draw_loc_rot_axis: bpr.BoolProperty(name = '', default = False, update= prop_update_draw_loc_rot_axis)

	loc_rot_presets: bpr.EnumProperty(
		items = enum_updateloc_rot_presets, name = 'Loc/Orient Presets', description = 'Preset')
	draw_loc_rot_presets: bpr.BoolProperty(default= False, update= prop_update_draw_loc_rot_presets)

	loc_mode: bpr.EnumProperty(items= [('1','Global','',1),('2','Local','',2)], update= prop_update_loc_mode)

	loc_x: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)
	loc_y: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)
	loc_z: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)

	loc_x_ltr: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6, update= prop_update_loc_ltr)
	loc_y_ltr: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6, update= prop_update_loc_ltr)
	loc_z_ltr: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6, update= prop_update_loc_ltr)

	rot_x: bpr.FloatProperty(subtype = 'ANGLE', min= -6.28319, max= 6.28319, update= prop_update_rot)
	rot_y: bpr.FloatProperty(subtype = 'ANGLE', min= -6.28319, max= 6.28319, update= prop_update_rot)
	rot_z: bpr.FloatProperty(subtype = 'ANGLE', min= -6.28319, max= 6.28319, update= prop_update_rot)

	z_rem: bpr.BoolProperty(name = 'Z+ Remap', description= 'Remap Z+ axis orientation (may be quite handy for certain cases)', default = False)

	z_axis: bpr.EnumProperty(name='',
		items= [('z+','Z+ Same','Z+ axis untached as it is.',1),
				('z-','Z- Axis','Z+ use Z- vector',2),
				('y+','Y+ Axis','Z+ use Y+ vector',3),
				('y-','Y- Axis','Z+ use Y+ vector',4),
				('x+','X+ Axis','Z+ use X+ vector',5),
				('x-','X- Axis','Z+ use X+ vector',6)], default= 'z+')
	rem_zp: bpr.EnumProperty(
		items= [('1','X+ same  | Y+ same ','',1),('2','X+ to Y+ | Y+ to X-','',2),
				('3','X+ to X- | Y+ to Y-','',3),('4','X+ to Y- | Y+ to X+','',4)], default= '1')
	rem_zn: bpr.EnumProperty(
		items= [('1','X+ same  | Y+ to Y-','',1),('2','X+ to Y+ | Y+ to X+','',2),
				('3','X+ to X- | Y+ same ','',3),('4','X+ to Y- | Y+ to X-','',4)], default= '1')
	rem_yp: bpr.EnumProperty(
		items= [('1','X+ same  | Y+ to Z-','',1),('2','X+ to Z+ | Y+ to X+','',2),
				('3','X+ to X- | Y+ to Z+','',3),('4','X+ to Z- | Y+ to X-','',4)], default= '1')
	rem_yn: bpr.EnumProperty(
		items= [('1','X+ same  | Y+ to Z+','',1),('2','X+ to Z+ | Y+ to X-','',2),
				('3','X+ to X- | Y+ to Z-','',3),('4','X+ to Z- | Y+ to X+','',4)], default= '1')
	rem_xp: bpr.EnumProperty(
		items= [('1','X+ to Z- | Y+ same ','',1),('2','X+ to Y+ | Y+ to Z+','',2),
				('3','X+ to Z+ | Y+ to Y-','',3),('4','X+ to Y- | Y+ to Z-','',4)], default= '1')
	rem_xn: bpr.EnumProperty(
		items= [('1','X+ to Z+ | Y+ same ','',1),('2','X+ to Y+ | Y+ to Z-','',2),
				('3','X+ to Z- | Y+ to Y-','',3),('4','X+ to Y- | Y+ to Z+','',4)], default= '1')


	spot_set_pick: bpr.EnumProperty(
		items= [('1','Set Origin','Set ORIGIN location to FIXED spot',1),
				('2','Pick Spot','Pick spots LOCATION values to Location & Orientation panel',2)], default= '1', update= prop_update_spot_set_pick)
	spot_set_mode: bpr.EnumProperty(
		items= [('1','Active','Set ORIGIN for ACTIVE object only',1),
				('2','Multi','Set ORIGINS for MULTIPLE objects as if they are single object',2),
				('3','To Active','Set ORIGINS of MULTIPLE objects to ACTIVE object spots',3),
				('4','For Each','Set ORIGINS for EACH object own spots in selection',4)], default= '1')
	spot_set_not_active: bpr.BoolProperty(name = '', description= 'ORIGIN transformation will not affect ACTIVE object', default = False)

	spot_set_axis: bpr.EnumProperty(items= [('1','X','',1),('2','Y','',2),('3','Z','',3)], description= 'Spots projection AXIS', default= '1')
	spot_set_dir: bpr.EnumProperty(items= [('1','Positive','',1),('2','Negative','',2)], description= 'Spots projection ORIENTATION', default= '1')
	spot_set_space: bpr.EnumProperty(items= [('1','Global','',1),('2','Local','',2),('3','View','',3),('4','Cursor','',4),('5','Preset','',5)],
									description= 'Spots projection SPACE')

	drop_to_mode: bpr.EnumProperty(
		items= [('1','Space','Drop ORIGIN to current SPACE',1),
				('2','Bound','Drop ORIGIN to current BOUND in current space',2)], default= '1')
	drop_to_smode: bpr.EnumProperty(
		items= [('1','Zero','Drop ORIGIN to selected SPACE zero',1),
				('2','Median','Drop ORIGIN to MEDIAN between selected objects (designed for multiple objects)',2)], default= '1')
	drop_to_offset: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)
	drop_custom_zero: bpr.BoolProperty(name= '', default=False)

	czp_x: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)
	czp_y: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)
	czp_z: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)

	draw_spots: bpr.BoolProperty(name = '', default = False, update= prop_update_draw_spots)
	draw_spots_recalc: bpr.BoolProperty(name = '', default = True, update= prop_update_draw_spots_recalc,
										description = 'Recalculate current mesh bound spots manually')
	draw_spots_scale: bpr.FloatProperty(default= 1,precision= 2,min= 0.1, max= 2)
	draw_opt_bndc: bpr.BoolProperty(name = '', default =True)
	draw_opt_bnds: bpr.BoolProperty(name = '', default =True)
	draw_opt_dtpl: bpr.BoolProperty(name = '', default =True)


ctr = [
	SOT_PT_Panel,
	SOT_PT_Location_Orientation,
	SOT_PT_Location,
	SOT_PT_Orientation,
	SOT_PT_Presets,
	SOT_PT_Fixed_Snap,

	SOT_OT_Preset_Ren,
	SOT_OT_Preset_Add,
	SOT_OT_Preset_Add_Cursor,
	SOT_OT_Preset_Add_Active,
	SOT_OT_Preset_Rem,
	SOT_OT_Preset_Rrd,
	SOT_OT_Preset_Get,
	SOT_OT_Set_Loc_Rot,
	SOT_OT_Get_Transform,
	SOT_OT_Rotate_Ninety,
	SOT_OT_Fixed_Snap,
	SOT_OT_Fixed_Spot_Pick,
	SOT_OT_Convert_Local,
	SOT_OT_Convert_From_Local,
	SOT_OT_Clear_Value,

	SOT_OT_Draw_Axis,
	SOT_OT_Draw_Presets,
	SOT_OT_Draw_Spots,

	SOT_PR_Settings_Props]

def register():
	for cls in ctr:
		bpy.utils.register_class(cls)
	bpy.types.Scene.sot_props = bpy.props.PointerProperty(type=SOT_PR_Settings_Props)

def unregister():
	for cls in reversed(ctr):
		bpy.utils.unregister_class(cls)
	del bpy.types.Scene.sot_props
