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
nvdata = np.empty(0, dtype=np.float32)
mnvdata = []
svdata = np.empty(0, dtype=np.float32)
msvdata = []
sps_data = []
sps_space = 'World'


def report(self,message):
	self.report({'ERROR'}, message)
	return{'CANCELLED'}

def unic_name_geterator(name, existing_names, exception = False, excepted_name = ''):
	name_is_unic = False
	first_check = True

	while not name_is_unic:
		name_is_unic = True
		for en in existing_names:
			if exception and name == excepted_name:
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

def set_origin_location(x,y,z,tob,bcv):
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
	tob.select_set(False)
	return

def set_origin_orientation(x,y,z,tob,bob):
	tob.select_set(True)
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
	tob.select_set(False)
	return

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
			print('else')
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

		else:
			vz = vector_fix(obm, bma.normal)
			if len(bma.verts)	== 3:
				vy = vector_fix(obm, (bma.calc_tangent_edge())*-1)
			elif len(bma.verts) == 4:
				vy = vector_fix(obm, ((bma.calc_tangent_edge_pair()).normalized())*-1)
			else:
				le,ei = 0,-1
				c = 0
				for i,e in enumerate(bma.edges):
					if e.calc_length() > le:
						le = e.calc_length()
						ei = i
				vy = ector_fix(obm, (bma.edges[ei].verts[0].co - bma.edges[ei].verts[1].co).normalized())
				vy = vy-(vy.dot(vz)*vz)
			vx = (vz.cross(vy))*-1

		vx,vy,vz = vectors_remap(vx,vy,vz,sot)

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

def set_manual_values(sot,value,loc):
	if loc:
		sot.loc_x,sot.loc_y,sot.loc_z = value
	else:
		if abs(value[0]) < 0.0001: value[0] = 0
		if abs(value[1]) < 0.0001: value[1] = 0
		if abs(value[2]) < 0.0001: value[2] = 0
		sot.rot_x,sot.rot_y,sot.rot_z = value
	return

def aob_check(aob):
	if aob == None: return (True,'No ACTIVE object in selection!!!!')
	else: return (False,'')

def mesh_check(cob):
	if cob.type != 'MESH': return (True,'One of selected objects is not MESH type.')
	else: return (False,'')

def get_snap_spot_active(bco,sot,aob):
	if bco.mode == 'EDIT_MESH':
		bmd = bmesh.from_edit_mesh(bco.edit_object.data)
		vdt = bmd.verts
	else:
		vdt = aob.data.vertices
	obm = aob.matrix_world
	sps = spots(sot,obm,vdt)
	psp = projection(sot,obm,sps)[0]
	psp['dtp'] = projection(sot,obm,sps)[2][1]
	return psp

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

def draw_axis_main(self,context):
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
	batch = batch_for_shader(shader, 'LINES', {"pos": vcm, "color": col})
	bgl.glLineWidth(5)
	shader.bind()
	batch.draw(shader)
	bgl.glLineWidth(1)
	return


def same_mts_check(sot,aob,sob):

	global sob_mts

	rewrite_mts = False
	same_mts = True

	if sot.active_batch_spot == '2' or (sot.active_batch_spot == '3' and sot.batch_spot_mode == '2'):
		for ob in sob:
			if ob.type == 'MESH':
				if (not ob.name in sob_mts.keys()) or (ob.matrix_world != sob_mts.get(ob.name)):
					sob_mts.clear()
					rewrite_mts = True
					same_mts = False
					break
	else:
		if aob.type == 'MESH':
			if not aob.name in sob_mts.keys() or aob.matrix_world != sob_mts.get(aob.name):
				sob_mts.clear()
				rewrite_mts = True
				same_mts = False			
	
	if rewrite_mts:
		for ob in sob:
			if ob.type == 'MESH':
				sob_mts[ob.name] = mu.Matrix(ob.matrix_world)

	return not same_mts

def get_ob_vdata(sot,aob,sob):

	global nvdata
	global mnvdata

	if sot.active_batch_spot == '1' or (sot.active_batch_spot == '3' and sot.batch_spot_mode == '1'):
		if bpy.context.mode == 'EDIT_MESH':
			bpy.context.active_object.update_from_editmode()

		v_num = len(aob.data.vertices)
		nvdata = np.empty(v_num*3, dtype=np.float32)
		aob.data.vertices.foreach_get('co',nvdata)
		nvdata = np.reshape(nvdata,(v_num,3))

		'''
		NOTE
		Переробити дет обжект під нові спот калькулейшени
		'''
	# elif sot.active_batch_spot == '2':
	# 	nvdata = np.empty(0, dtype=np.float32)
	# 	for ob in sob:
	# 		if ob.type == 'MESH':
	# 			if ob.mode == 'EDIT':
	# 				ob.update_from_editmode()
	# 			v_num = len(ob.data.vertices)
	# 			tvdata = np.empty(v_num*3, dtype=np.float32) 
	# 			ob.data.vertices.foreach_get('co',tvdata)
	# 			nvdata = np.append(nvdata,tvdata)
	# 	nvdata = np.reshape(nvdata,(nvdata.size//3,3))

	else:
		for ob in sob:
			if ob.type == 'MESH':
				if ob.mode == 'EDIT':
					ob.update_from_editmode()
				v_num = len(ob.data.vertices)
				tvdata = np.empty(v_num*3, dtype=np.float32)
				ob.data.vertices.foreach_get('co',tvdata)
				tvdata = np.reshape(tvdata,(v_num,3))
				mnvdata.append((ob.matrix_world,tvdata))

def same_vdata_check(sot):

	global nvdata
	global mnvdata
	global svdata
	global msvdata

	if sot.active_batch_spot == '3' and sot.batch_spot_mode == '2':
		if not np.array_equal(mnvdata, msvdata, equal_nan=False):
			msvdata = mnvdata
			return True

	else:	
		if not np.array_equal(nvdata, svdata, equal_nan=False):
			svdata = nvdata
			return True


def vco(coord,v,b,value,vector,count):
	if b:
		if round(coord[v],4) >= value:
			value = round(coord[v],4)
			if value == round(vector[v]/count,4):
				vector = vector + coord
				count += 1
			else:
				vector = coord
				count = 1
	else:
		if round(coord[v],4) <= value:
			value = round(coord[v],4)
			if value == round(vector[v]/count,4):
				vector = vector + coord
				count += 1
			else:
				vector = coord
				count = 1
	return value,vector,count

def vcv(co,v,a,av,avv,avc,adv):
	av = a
	if abs(av - round(avv[v]/avc,4)) <= adv:
		avv,avc = avv+co,avc+1 	 
	else:
		avv,avc = co,1

	return av,avv,avc

'''
1. Active:
	- Global | Спочатку всі споти рахуються з уразуванням матриці рот/скейл
2. Multi:
	- Calculeta spots for many objects, each objects has own world matrix.
	- Then apply on it orientation matrix from transform orientation for active object.
3. Batch:
	- Active - same as for Active
	- For each object with own world matrix
'''

def spots(sot,obm,vdata):

	obm_t = obm.to_3x3()
	obm_r = obm.to_euler()

	fv = obm_t @ vdata[0].co if sot.set_spot_space == '1' else vdata[0].co
	xn,xp,yn,yp,zn,zp = round(fv[0],4),round(fv[0],4),round(fv[1],4),round(fv[1],4),round(fv[2],4),round(fv[2],4)
	xnv,xpv,ynv,ypv,znv,zpv,csm = fv,fv,fv,fv,fv,fv,fv
	xnc = xpc = ync = ypc = znc = zpc = 1

	adx = round(0.0002 + (0.0012 * (abs(obm_r[1]/3.1416) + abs(obm_r[2]/3.1416))),4)
	ady = round(0.0002 + (0.0012 * (abs(obm_r[0]/3.1416) + abs(obm_r[2]/3.1416))),4)
	adz = round(0.0002 + (0.0012 * (abs(obm_r[0]/3.1416) + abs(obm_r[1]/3.1416))),4)

	for v in vdata[1:]:
		co = obm_t @ v.co if sot.set_spot_space == '1' else v.co
		x,y,z = round(co[0],4),round(co[1],4),round(co[2],4)

		if x >= xp - (adx*abs(xp/1000)) : xp,xpv,xpc = vcv(co,0,x,xp,xpv,xpc,adx)
		if x <= xn + (adx*abs(xn/1000)) : xn,xnv,xnc = vcv(co,0,x,xn,xnv,xnc,adx)
		if y >= yp - (ady*abs(yp/1000)) : yp,ypv,ypc = vcv(co,1,y,yp,ypv,ypc,ady)
		if y <= yn + (ady*abs(yn/1000)) : yn,ynv,ync = vcv(co,1,y,yn,ynv,ync,ady)
		if z >= zp - (adz*abs(zp/1000)) : zp,zpv,zpc = vcv(co,2,z,zp,zpv,zpc,adz)
		if z <= zn + (adz*abs(zn/1000)) : zn,znv,znc = vcv(co,2,z,zn,znv,znc,adz)

		csm = csm + co

	boc = mu.Vector((((xn+xp)/2),((yn+yp)/2),((zn+zp)/2)))
	com = csm/len(vdata)

	if xnc != 1: xnv = xnv/xnc
	if xpc != 1: xpv = xpv/xpc
	if ync != 1: ynv = ynv/ync
	if ypc != 1: ypv = ypv/ypc
	if znc != 1: znv = znv/znc
	if zpc != 1: zpv = zpv/zpc

	sps = {'xn':xn,'xp':xp,'yn':yn,'yp':yp,'zn':zn,'zp':zp,'boc':boc,'com':com,
			'xnv':xnv,'xpv':xpv,'ynv':ynv,'ypv':ypv,'znv':znv,'zpv':zpv,}

	return sps

def get_dtp_b(axis,sot,dtp_a,v,vc,loc,off):
	dtp = mu.Vector(dtp_a[:])
	pos = loc[axis] if sot.set_spot_space == '1' else 0
	if sot.drop_to_mode == '1':   dtp[axis] = off
	elif sot.drop_to_mode == '2': dtp[axis] = pos + v + off
	else: dtp[axis] = pos + vc + off
	return dtp

def projection(sot,obm,sps):

	loc = mu.Vector(obm.col[3][:3])

	xn,xp,yn,yp,zn,zp,boc = sps.get('xn'),sps.get('xp'),sps.get('yn'),sps.get('yp'),sps.get('zn'),sps.get('zp'),sps.get('boc')
	xc,yc,zc = boc[0],boc[1],boc[2]
	dtp_a = loc if sot.set_spot_space == '1' else mu.Vector((0,0,0))

	if sot.set_spot_dir == '1': x,y,z = xp,yp,zp
	else: x,y,z = xn,yn,zn

	off = sot.drop_to_offset 
	if sot.drop_to_mode != '1' and sot.set_spot_dir == '2': off = off * -1

	#dtp_b = mu.Vector((0,0,0))

	if sot.set_spot_axis == '1': # drop to world
		dtp_b = get_dtp_b(0,sot,dtp_a,x,xc,loc,off)
		psp =  {'np':mu.Vector((x,yn,zp)),'cp':mu.Vector((x,yc,zp)),'pp':mu.Vector((x,yp,zp)),
				'nc':mu.Vector((x,yn,zc)),'cc':mu.Vector((x,yc,zc)),'pc':mu.Vector((x,yp,zc)),
				'nn':mu.Vector((x,yn,zn)),'cn':mu.Vector((x,yc,zn)),'pn':mu.Vector((x,yp,zn))}
	elif sot.set_spot_axis == '2': # drop to bound
		dtp_b = get_dtp_b(1,sot,dtp_a,y,yc,loc,off)
		psp =  {'np':mu.Vector((xn,y,zp)),'cp':mu.Vector((xc,y,zp)),'pp':mu.Vector((xp,y,zp)),
				'nc':mu.Vector((xn,y,zc)),'cc':mu.Vector((xc,y,zc)),'pc':mu.Vector((xp,y,zc)),
				'nn':mu.Vector((xn,y,zn)),'cn':mu.Vector((xc,y,zn)),'pn':mu.Vector((xp,y,zn))}
	else: # drop to median
		dtp_b = get_dtp_b(2,sot,dtp_a,z,zc,loc,off)
		psp =  {'np':mu.Vector((xn,yp,z)),'cp':mu.Vector((xc,yp,z)),'pp':mu.Vector((xp,yp,z)),
				'nc':mu.Vector((xn,yc,z)),'cc':mu.Vector((xc,yc,z)),'pc':mu.Vector((xp,yc,z)),
				'nn':mu.Vector((xn,yn,z)),'cn':mu.Vector((xc,yn,z)),'pn':mu.Vector((xp,yn,z))}

	if sot.set_spot_axis == '1':
		bom = sps.get('xpv') if sot.set_spot_dir == '1' else sps.get('xnv')
	elif sot.set_spot_axis == '2':
		bom = sps.get('ypv') if sot.set_spot_dir == '1' else sps.get('ynv')
	else:
		bom = sps.get('zpv') if sot.set_spot_dir == '1' else sps.get('znv')

	psp['bom'] = bom
	psp['boc'] = sps.get('boc')
	psp['com'] = sps.get('com')


	# combine cage coords from spots data
	cage = [mu.Vector((xn,yn,zn)),mu.Vector((xn,yn,zp)),
			mu.Vector((xn,yn,zp)),mu.Vector((xn,yp,zp)),
			mu.Vector((xn,yp,zp)),mu.Vector((xn,yp,zn)),
			mu.Vector((xn,yp,zn)),mu.Vector((xn,yn,zn)),
			mu.Vector((xp,yn,zn)),mu.Vector((xp,yn,zp)),
			mu.Vector((xp,yn,zp)),mu.Vector((xp,yp,zp)),
			mu.Vector((xp,yp,zp)),mu.Vector((xp,yp,zn)),
			mu.Vector((xp,yp,zn)),mu.Vector((xp,yn,zn)),
			mu.Vector((xn,yn,zn)),mu.Vector((xp,yn,zn)),
			mu.Vector((xn,yn,zp)),mu.Vector((xp,yn,zp)),
			mu.Vector((xn,yp,zp)),mu.Vector((xp,yp,zp)),
			mu.Vector((xn,yp,zn)),mu.Vector((xp,yp,zn))]

	# dtp - drop to point (points A and B)
	dtp = [dtp_a,dtp_b]

	for k,v in psp.items():
		psp[k] = obm @ v if sot.set_spot_space == '2' else loc + v
	for i,v in enumerate(cage):
		cage[i] = obm @ v if sot.set_spot_space == '2' else loc + v
	for i,v in enumerate(dtp):
		if sot.set_spot_space == '2': 
			dtp[i] = obm @ v
		#elif i == 1: dtp[i] = v + loc

	return psp,cage,dtp

def projection_multi(sot,obm,sps):

	loc = mu.Vector(obm.col[3][:3])

	xn,xp,yn,yp,zn,zp,boc = sps.get('xn'),sps.get('xp'),sps.get('yn'),sps.get('yp'),sps.get('zn'),sps.get('zp'),sps.get('boc')
	xc,yc,zc = boc[0],boc[1],boc[2]
	dtp_a = loc if sot.set_spot_space == '1' else mu.Vector((0,0,0))

	if sot.set_spot_dir == '1': x,y,z = xp,yp,zp
	else: x,y,z = xn,yn,zn

	off = sot.drop_to_offset 
	if sot.drop_to_mode != '1' and sot.set_spot_dir == '2': off = off * -1

	#dtp_b = mu.Vector((0,0,0))

	if sot.set_spot_axis == '1':
		dtp_b = get_dtp_b(0,sot,dtp_a,x,xc,loc,off)
		psp =  {'np':mu.Vector((x,yn,zp)),'cp':mu.Vector((x,yc,zp)),'pp':mu.Vector((x,yp,zp)),
				'nc':mu.Vector((x,yn,zc)),'cc':mu.Vector((x,yc,zc)),'pc':mu.Vector((x,yp,zc)),
				'nn':mu.Vector((x,yn,zn)),'cn':mu.Vector((x,yc,zn)),'pn':mu.Vector((x,yp,zn))}
	elif sot.set_spot_axis == '2':
		dtp_b = get_dtp_b(1,sot,dtp_a,y,yc,loc,off)
		psp =  {'np':mu.Vector((xn,y,zp)),'cp':mu.Vector((xc,y,zp)),'pp':mu.Vector((xp,y,zp)),
				'nc':mu.Vector((xn,y,zc)),'cc':mu.Vector((xc,y,zc)),'pc':mu.Vector((xp,y,zc)),
				'nn':mu.Vector((xn,y,zn)),'cn':mu.Vector((xc,y,zn)),'pn':mu.Vector((xp,y,zn))}
	else:
		dtp_b = get_dtp_b(2,sot,dtp_a,z,zc,loc,off)
		psp =  {'np':mu.Vector((xn,yp,z)),'cp':mu.Vector((xc,yp,z)),'pp':mu.Vector((xp,yp,z)),
				'nc':mu.Vector((xn,yc,z)),'cc':mu.Vector((xc,yc,z)),'pc':mu.Vector((xp,yc,z)),
				'nn':mu.Vector((xn,yn,z)),'cn':mu.Vector((xc,yn,z)),'pn':mu.Vector((xp,yn,z))}

	if sot.set_spot_axis == '1':
		bom = sps.get('xpv') if sot.set_spot_dir == '1' else sps.get('xnv')
	elif sot.set_spot_axis == '2':
		bom = sps.get('ypv') if sot.set_spot_dir == '1' else sps.get('ynv')
	else:
		bom = sps.get('zpv') if sot.set_spot_dir == '1' else sps.get('znv')

	psp['bom'] = bom
	psp['boc'] = sps.get('boc')
	psp['com'] = sps.get('com')

	cage = [mu.Vector((xn,yn,zn)),mu.Vector((xn,yn,zp)),
			mu.Vector((xn,yn,zp)),mu.Vector((xn,yp,zp)),
			mu.Vector((xn,yp,zp)),mu.Vector((xn,yp,zn)),
			mu.Vector((xn,yp,zn)),mu.Vector((xn,yn,zn)),
			mu.Vector((xp,yn,zn)),mu.Vector((xp,yn,zp)),
			mu.Vector((xp,yn,zp)),mu.Vector((xp,yp,zp)),
			mu.Vector((xp,yp,zp)),mu.Vector((xp,yp,zn)),
			mu.Vector((xp,yp,zn)),mu.Vector((xp,yn,zn)),
			mu.Vector((xn,yn,zn)),mu.Vector((xp,yn,zn)),
			mu.Vector((xn,yn,zp)),mu.Vector((xp,yn,zp)),
			mu.Vector((xn,yp,zp)),mu.Vector((xp,yp,zp)),
			mu.Vector((xn,yp,zn)),mu.Vector((xp,yp,zn))]

	dtp = [dtp_a,dtp_b]

	for k,v in psp.items():
		psp[k] = obm @ v if sot.set_spot_space == '2' else loc + v
	for i,v in enumerate(cage):
		cage[i] = obm @ v if sot.set_spot_space == '2' else loc + v
	for i,v in enumerate(dtp):
		if sot.set_spot_space == '2': 
			dtp[i] = obm @ v
		#elif i == 1: dtp[i] = v + loc
			

	return psp,cage,dtp

mc = {}

def draw_spots_main(self,context):
	bco = bpy.context
	sot = context.scene.sot_props
	bcv = bco.view_layer
	aob = bco.active_object
	sob = bco.selected_objects

	global sps_space
	global sps_data
	global svdata
	global msvdata

	goon = False

	if sot.active_batch_spot == '1' or (sot.active_batch_spot == '3' and sot.batch_spot_mode == '1'):
		if aob != None and aob.type == 'MESH':
			goon = True
	elif 'MESH' in [ob.type for ob in sob]:
		goon = True

	if goon:
		obm = aob.matrix_world

		spots_recalc = False

		if sot.set_spot_space != sps_space:
			sps_space = sot.set_spot_space
			spots_recalc = True

		elif sot.spots_auto == '1' or sot.manual_recalc:	
			spots_recalc = same_mts_check(sot,aob,sob)
			if not spots_recalc:
				get_ob_vdata(sot,aob,sob)
				spots_recalc = same_vdata_check(sot)

		if spots_recalc:
			if sot.active_batch_spot == '3' and sot.batch_spot_mode == '2':
				print('\nMSVDATA')
				print(msvdata)
			else:
				print('\nSVDATA')
				print(svdata)

			# if sot.active_batch_spot == '3' and sot.batch_spot_mode == '2':
			# 	sps_data.clear()
			# 	for ob in sob:
			# 		if ot.type == 'MESH':
			# 			sps_data.append(spots(sot,obm,nvdata))
			# else:
			# 	sps_data.clear()
			# 	sps_data.append(spots(sot,obm,nvdata))

		sot.manual_recalc = False

#-----------------------------------------------------------

		
		'''
		NOTE
		Виключений дров кейдж, до переробки спотів/прожекшенів
		'''

		# psp,cage,dtp = projection(sot,obm,sps)
		# vmt = bco.area.spaces.active.region_3d.view_matrix
		# vmtr = vmt.to_3x3().inverted()

		# shader = gpu.shader.from_builtin('3D_SMOOTH_COLOR')

		# sva =  [(-0.2,0,0),(-0.05,0,0),
		# 		(0.05,0,0),(0.2,0,0),
		# 		(0,0,0),(-0.1,0.1,0),
		# 		(-0.1,0.1,0),(0.1,0.1,0),
		# 		(0.1,0.1,0),(0,0,0)]

		# svb =  [(-0.1,0,0),(0,0.1,0),
		# 		(0,0.1,0),(0.1,0,0),
		# 		(0.1,0,0),(0,-0.1,0),
		# 		(0,-0.1,0),(-0.1,0,0)]

		# svc =  [(-0.1,-0.1,0),(-0.1,0.1,0),
		# 		(-0.1,0.1,0),(0.1,0.1,0),
		# 		(0.1,0.1,0),(0.1,-0.1,0),
		# 		(0.1,-0.1,0),(-0.1,-0.1,0)]

		# svd =  [(-0.1,-0.1,0),(0,0,0),
		# 		(0,0,0),(0.1,-0.1,0),
		# 		(0.1,-0.1,0),(-0.1,-0.1,0)]

		# #Colors = white spots, border mesh spot, bound center spot, center of mass spot, 
		# #		  X, Y, Z axis colors
		# c = [(1.0, 1.0, 1.0, 1.0),(0, 0.9, 1.0, 1.0),(0.9, 0.2, 0.2, 1.0),(1.0, 0.5, 0.05, 1.0),
		# 	 (1.0, 0.2, 0.2, 1.0),(0.4, 1, 0.0, 1.0),(0.0 , 0.5, 1.0, 1.0)]


		# if sot.set_spot_axis == '1': ca = [c[4],c[5],c[6]]
		# elif sot.set_spot_axis == '2': ca = [c[5],c[4],c[6]]
		# else: ca = [c[6],c[4],c[5]]

		# csd = {'np':(ca[2],2.2,svd),'cp':(c[0],1,svb),'pp':(c[0],1,svb),
		# 		'nc':(ca[2],2.2,svc),'cc':(c[0],1,svb),'pc':(c[0],1,svb),
		# 		'nn':(ca[0],2.2,svc),'cn':(ca[1],2.2,svc),'pn':(ca[1],2.2,svc),
		# 		'bom':(c[1],2,svb),'boc':(c[2],3.5,svb),'com':(c[3],2.7,svb)}
		# cc = (1.0, 1.0, 1.0, 1.0)

		# for key,vec in psp.items():
		# 	vcm = []
		# 	col = []

		# 	scl = screen_size(bco,vec,True) * csd.get(key)[1] * sot.spots_scale
		# 	for v in csd.get(key)[2]:
		# 		v = (vmtr @ (mu.Vector(v)*scl)) + vec	
		# 		vcm.append(v)
		# 		col.append(csd.get(key)[0])

		# 	batch = batch_for_shader(shader, 'LINES', {"pos": vcm, "color": col})
		# 	bgl.glLineWidth(4)
		# 	shader.bind()
		# 	batch.draw(shader)
		# 	bgl.glLineWidth(1)

		# vcm = []
		# col = []
		# for v in cage:
		# 	vcm.append(v)
		# 	col.append((1,1,0,1)) # Cage color

		# batch = batch_for_shader(shader, 'LINES', {"pos": vcm, "color": col})
		# bgl.glLineWidth(1)
		# shader.bind()
		# batch.draw(shader)
		# bgl.glLineWidth(1)

		# vcm = []
		# col = []
		# for i,v in enumerate(dtp):
		# 	vcm.append(v)
		# 	col.append((1,1,1,1))

		# 	if i == 1:
		# 		scl = screen_size(bco,v,True) * 2 * sot.spots_scale
		# 		for c in sva:
		# 			c = (vmtr @ (mu.Vector(c)*scl)) + v
		# 			vcm.append(c)
		# 			col.append((1, 0.2, 1.0, 1.0)) # Drop spot color

		# batch = batch_for_shader(shader, 'LINES', {"pos": vcm, "color": col})
		# bgl.glLineWidth(3)
		# shader.bind()
		# batch.draw(shader)
		# bgl.glLineWidth(1)

	return

def enum_update_presets(self, context):
	pr_enum = []
	pr_num = len(pr_values)
	for k,v in pr_values.items():
		n = len(pr_enum)
		new_pr = (k, k, 'Location = ' + str(v[0]) + ' | Orientation = ' 
			+ str((round(math.degrees(v[1][0]),4),round(math.degrees(v[1][1]),4),round(math.degrees(v[1][2]),4))), n)
		pr_enum.append(new_pr)
	return pr_enum

def prop_update_draw_axis(self, context):
	if context.scene.sot_props.draw_axis:
		bpy.ops.fgt.sot_draw_axis('INVOKE_DEFAULT')
	return

def prop_update_manual_recalc(self,context):
	sot =  context.scene.sot_props
	if not sot.draw_spots and sot.manual_recalc:
		sot.manual_recalc = False
	return

def prop_update_draw_spots(self, context):
	sot =  context.scene.sot_props
	if sot.draw_spots:
		if sot.spots_auto == '2' and sot.manual_recalc == False:
			 sot.manual_recalc = True
		bpy.ops.fgt.sot_draw_spots('INVOKE_DEFAULT')
	return

def prop_update_set_pick(self, context):
	sot =  context.scene.sot_props
	if sot.set_pick == '2' and (sot.spots_snap_mode == '3' or sot.spots_snap_mode == '4'):
		sot.spots_snap_mode = '2'
	return



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
		layout = self.layout
		col = layout.column(align=True)

		row = col.row(align=True)
		row.label(text= 'Set Origin:')
		if pr_values != {}: row.prop(sot, 'from_preset', text= 'From Preset', icon='PASTEFLIPDOWN', toggle= True)
		row = col.row(align=True)

		set_loc = row.operator('fgt.sot_set_origin_loc_rot', icon='ORIENTATION_GLOBAL', text='Location')
		set_loc.prm_set_loc_rot = 'Loc'
		set_loc.prm_set_act_bat = sot.active_batch
		set_loc.prm_set_location = mu.Vector((sot.loc_x,sot.loc_y,sot.loc_z))
		set_loc.prm_set_rotation = mu.Vector((sot.rot_x,sot.rot_y,sot.rot_z))	

		set_rot = row.operator('fgt.sot_set_origin_loc_rot', icon='ORIENTATION_GIMBAL', text='Orientation')
		set_rot.prm_set_loc_rot = 'Rot'
		set_rot.prm_set_act_bat = sot.active_batch
		set_rot.prm_set_location = mu.Vector((sot.loc_x,sot.loc_y,sot.loc_z))
		set_rot.prm_set_rotation = mu.Vector((sot.rot_x,sot.rot_y,sot.rot_z))

		set_both = col.operator('fgt.sot_set_origin_loc_rot', icon='ORIENTATION_LOCAL', text='Location + Orientation')
		set_both.prm_set_loc_rot = 'Loc + Rot'
		set_both.prm_set_act_bat = sot.active_batch
		set_both.prm_set_location = mu.Vector((sot.loc_x,sot.loc_y,sot.loc_z))
		set_both.prm_set_rotation = mu.Vector((sot.rot_x,sot.rot_y,sot.rot_z))

		col.separator(factor=1)

		row = col.row(align=True)
		row.prop_enum(sot, 'active_batch', icon= 'DOT', value= '1')
		row.prop_enum(sot, 'active_batch', icon= 'LIGHTPROBE_GRID', value= '2')
		row = col.row(align=True)
		row.prop(sot, 'draw_axis', text= 'Hide Helper Axis' if sot.draw_axis else 'Show Helper Axis', icon='EMPTY_AXIS', toggle= True)

class SOT_PT_Presets(bpy.types.Panel):
	bl_label = 'Presets'
	bl_idname = 'SOT_PT_Presets'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'FGT'
	bl_parent_id = 'SOT_PT_Location_Orientation'
	bl_options = {'DEFAULT_CLOSED'}

	def draw(self, context):
		sot = context.scene.sot_props
		layout = self.layout
		col = layout.column(align=True)

		row = col.row(align=True)
		row.operator('fgt.sot_preset_ren', text='', icon='EVENT_R')
		row.prop(sot, 'presets', text = '')
		row.operator('fgt.sot_preset_add', text='', icon='IMPORT')
		row.operator('fgt.sot_preset_rem', text='', icon='X' if len(pr_values) != 0 else 'DOT')
		row = col.row(align=True)
		row.operator('fgt.sot_preset_get', text='', icon='EXPORT')			.prm_preset_get = 'both'
		row.operator('fgt.sot_preset_get', text='Loc', icon='EXPORT')		.prm_preset_get = 'loc'
		row.operator('fgt.sot_preset_get', text='Rot', icon='EXPORT')		.prm_preset_get = 'rot'
		row.operator('fgt.sot_preset_rrd', text='', icon='TRIA_UP')			.reorder_up = True
		row.operator('fgt.sot_preset_rrd', text='', icon='TRIA_DOWN')		.reorder_up = False
		if pr_values != {}:
			i = sot.presets
			v = pr_values.get(i)
			col.label(text= str(list(pr_values.keys()).index(i)+1) + '/' + str(len(pr_values)) + ' : ' + i)
			col.label(text= 'Loc ( X ' + str(round(v[0][0],5)) + ' | Y ' + str(round(v[0][1],5)) + ' | Z ' + str(round(v[0][2],5)) + ' )' )
			col.label(text= 'Rot ( X ' + str(round(math.degrees(v[1][0]),5)) + ' | Y ' + str(round(math.degrees(v[1][1]),5)) + ' | Z ' + str(round(math.degrees(v[1][2]),5)) + ' )' )

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

		col.label(text= 'Location Values')
		row = col.row(align=True)
		row.prop(sot, 'loc_x', text= 'X') 	
		row.operator(clear, icon='X' if sot.loc_x != 0 else 'DOT', text='')		.cop = 'loc_x'
		row = col.row(align=True)
		row.prop(sot, 'loc_y', text= 'Y')
		row.operator(clear, icon='X' if sot.loc_y != 0 else 'DOT', text='')		.cop = 'loc_y'
		row = col.row(align=True)			
		row.prop(sot, 'loc_z', text= 'Z')
		row.operator(clear, icon='X' if sot.loc_z != 0 else 'DOT', text='')		.cop = 'loc_z'
		col.separator(factor=1)

		row = col.row(align=True)
		row.operator('fgt.sot_set_origin_loc_rot', icon='TRANSFORM_ORIGINS', text='Set Origin Location').prm_set_loc_rot = 'Loc'
		row = col.row(align=True)
		row.operator(get, icon='PIVOT_CURSOR', text='Get Cursor')				.prm_get_transform = 'loc_c'
		row.operator(get, icon='PIVOT_ACTIVE', text='Get Active')				.prm_get_transform = 'loc_a'

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
		row.label(text= 'Rotation Values')
		row = col.row(align=True)
		row.operator(rotate, icon='LOOP_FORWARDS', text='')						.rop = '-rot_x'
		row.operator(rotate, icon='LOOP_BACK',     text='')						.rop = '+rot_x'
		row.prop(sot, 'rot_x', text= 'X')
		row.operator(clear, icon='X' if sot.rot_x != 0 else 'DOT', text='')		.cop = 'rot_x'
		row = col.row(align=True)
		row.operator(rotate, icon='LOOP_FORWARDS', text='')						.rop = '-rot_y'
		row.operator(rotate, icon='LOOP_BACK',     text='')						.rop = '+rot_y'
		row.prop(sot, 'rot_y', text= 'Y')
		row.operator(clear, icon='X' if sot.rot_y != 0 else 'DOT', text='')		.cop = 'rot_y'
		row = col.row(align=True)
		row.operator(rotate, icon='LOOP_FORWARDS', text='')						.rop = '-rot_z'
		row.operator(rotate, icon='LOOP_BACK',     text='')						.rop = '+rot_z'
		row.prop(sot, 'rot_z', text= 'Z')
		row.operator(clear, icon='X' if sot.rot_z != 0 else 'DOT', text='')		.cop = 'rot_z'
		col.separator(factor=1)
		

		row = col.row(align=True)
		row.operator('fgt.sot_set_origin_loc_rot', icon='ORIENTATION_GIMBAL', text='Set Origin Orientation').prm_set_loc_rot = 'Loc'
		row = col.row(align=True)
		row.operator(get, icon='PIVOT_CURSOR', text='Get Cursor')				.prm_get_transform = 'rot_c'
		row.operator(get, icon='PIVOT_ACTIVE', text='Get Active')				.prm_get_transform = 'rot_a'

		row = col.row(align=True)
		row.label(text= 'Z+ remap to:')
		row.prop(sot, 'z_axis', text= '')
		row.operator(clear, icon='X' if sot.z_axis != 'z+' else 'DOT', text='')	.cop = 'z_axis'
		row = col.row(align=True)
		row.prop(sot, zax_dic.get(sot.z_axis), text= '')
		row.operator(clear, icon='X' if rem_dic.get(sot.z_axis) != '1' else 'DOT', text='').cop = zax_dic.get(sot.z_axis)

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

		layout = self.layout
		col = layout.column(align=True)

		row = col.row(align=True)
		row.prop_enum(sot, 'set_pick', icon='TRANSFORM_ORIGINS', value= '1')
		row.prop_enum(sot, 'set_pick', icon='EXPORT', value= '2')
		row = col.row(align=True)
		row.prop_enum(sot, 'spots_snap_mode', icon='DOT', value= '1')
		row.prop_enum(sot, 'spots_snap_mode', icon='STICKY_UVS_LOC', value= '2')
		if sot.set_pick == '1':
			row = col.row(align=True)
			row.prop_enum(sot, 'spots_snap_mode', icon='PARTICLE_DATA', value= '3')
			row.prop_enum(sot, 'spots_snap_mode', icon='STICKY_UVS_DISABLE', value= '4')
			if sot.spots_snap_mode == '3':
				 row = col.row(align=True)
				 row.prop(sot, 'not_active', text= 'Exclude Active', icon= 'CANCEL', toggle= True)	
		col.separator(factor=1)

		row = col.row(align=True)
		row.prop_enum(sot, 'set_spot_axis', value= '1')
		row.prop_enum(sot, 'set_spot_axis', value= '2')
		row.prop_enum(sot, 'set_spot_axis', value= '3')
		row = col.row(align=True)
		row.prop_enum(sot, 'set_spot_dir', icon='ADD', value= '1')
		row.prop_enum(sot, 'set_spot_dir', icon='REMOVE', value= '2')
		row = col.row(align=True)
		row.prop_enum(sot, 'set_spot_space', icon='ORIENTATION_GLOBAL', value= '1')
		row.prop_enum(sot, 'set_spot_space', icon='ORIENTATION_LOCAL', value= '2')
		row = col.row(align=True)
		row.prop_enum(sot, 'set_spot_space', icon='ORIENTATION_VIEW', value= '3')
		row.prop_enum(sot, 'set_spot_space', icon='ORIENTATION_CURSOR', value= '4')
		
		cto = context.scene.transform_orientation_slots[0]
		row = col.row(align=True)
		row.enabled = not cto.custom_orientation == None
		custom_to = cto.type + ' Custom TO' if not cto.custom_orientation == None else 'Select Custom TO'
		row.prop_enum(sot, 'set_spot_space', icon='EMPTY_AXIS', text=custom_to, value= '5')
		col.separator(factor=1)

		row = col.row(align=True)
		row.operator('fgt.sot_fixed_snap', icon='TRIA_UP', text='')								.prm_set_spot_d = 'np'
		row.operator('fgt.sot_fixed_snap', icon='KEYFRAME', text='')							.prm_set_spot_d = 'cp'
		row.operator('fgt.sot_fixed_snap', icon='KEYFRAME', text='')							.prm_set_spot_d = 'pp'
		row.operator('fgt.sot_fixed_snap', icon='KEYTYPE_BREAKDOWN_VEC', text='Border Mesh')	.prm_set_spot_d = 'bom'
		row = col.row(align=True)
		row.operator('fgt.sot_fixed_snap', icon='HANDLETYPE_VECTOR_VEC', text='')				.prm_set_spot_d = 'nc'
		row.operator('fgt.sot_fixed_snap', icon='KEYFRAME', text='')							.prm_set_spot_d = 'cc'
		row.operator('fgt.sot_fixed_snap', icon='KEYFRAME', text='')							.prm_set_spot_d = 'pc'
		row.operator('fgt.sot_fixed_snap', icon='KEYTYPE_EXTREME_VEC', text='Bound Center')		.prm_set_spot_d = 'boc'
		row = col.row(align=True)
		row.operator('fgt.sot_fixed_snap', icon='HANDLETYPE_VECTOR_VEC', text='')				.prm_set_spot_d = 'nn'
		row.operator('fgt.sot_fixed_snap', icon='HANDLETYPE_VECTOR_VEC', text='')				.prm_set_spot_d = 'cn'
		row.operator('fgt.sot_fixed_snap', icon='HANDLETYPE_VECTOR_VEC', text='')				.prm_set_spot_d = 'pn'
		row.operator('fgt.sot_fixed_snap', icon='KEYTYPE_KEYFRAME_VEC', text='Center Of Mass')	.prm_set_spot_d = 'com'
		col.separator(factor=1)

		row = col.row(align=True)
		row.operator('fgt.sot_fixed_snap', icon='TRIA_DOWN_BAR', text='Drop To')				.prm_set_spot_d = 'dtp'
		row = col.row(align=True)
		row.prop_enum(sot, 'drop_to_mode', icon='SNAP_PERPENDICULAR', value= '1')
		row.prop_enum(sot, 'drop_to_mode', icon='SNAP_FACE_CENTER', value= '2')
		if sot.drop_to_mode == '1':
			row = col.row(align=True)
			row.prop_enum(sot, 'drop_to_space_sub', icon='EMPTY_AXIS', value= '1')
			row.prop_enum(sot, 'drop_to_space_sub', icon='NLA_PUSHDOWN', value= '2')
		else:
			row = col.row(align=True)
			row.prop_enum(sot, 'drop_to_bound_sub', icon='MOD_EDGESPLIT', value= '1')
			row.prop_enum(sot, 'drop_to_bound_sub', icon='ALIGN_MIDDLE', value= '2')



		row = col.row(align=True)
		row.prop(sot, 'drop_to_offset', text= 'Offset')
		row.operator(clear, icon='X' if sot.drop_to_offset != 0 else 'DOT', text='').cop = 'drop_to_offset'
		col.separator(factor=1)

		col.prop(sot, 'draw_spots', text= 'Hide Cage/Spots' if sot.draw_spots else 'Show Cage/Spots', 
			icon='RADIOBUT_OFF' if not sot.draw_spots else 'RADIOBUT_ON', toggle= True)
		if sot.draw_spots:
			col.prop(sot, 'manual_recalc', text= 'Refresh', icon='FILE_REFRESH', toggle= True)
			row = col.row(align=True)
			row.prop(sot, 'spots_scale', text= 'Spots Scale')
			row.operator(clear, icon='X' if sot.spots_scale != 1 else 'DOT', text='').cop = 'spots_scale'






# OPERATORES------------------------------------------------------------------------------------------------------




class SOT_OT_Preset_Ren(bpy.types.Operator):
	bl_idname = 'fgt.sot_preset_ren'
	bl_label = 'Rename Preset'
	bl_description = 'Rename selected preset'

	prm_new_name: bpr.StringProperty(default= 'New Name', name = '')

	def execute(self, context):
		sot = context.scene.sot_props
		new_name = self.prm_new_name
		new_values = {}
		global pr_values

		if new_name == '': return report(self,'Please enter at least something')

		for k,v in pr_values.items():
			if k != sot.presets: 
				new_values[k] = v
			else: 
				new_name = unic_name_geterator(new_name,pr_values.keys(),True,sot.presets)
				new_values[new_name] = v
		pr_values = new_values

		return{'FINISHED'}

	def invoke(self, context, event):
		if len(pr_values) != 0: return context.window_manager.invoke_props_dialog(self, width=150)
		else: return report(self,'Presets list is empty')	



class SOT_OT_Preset_Add(bpy.types.Operator):
	bl_idname = 'fgt.sot_preset_add'
	bl_label = 'New Preset Name'
	bl_description = 'Save values as:'

	prm_name: bpr.StringProperty(default= 'Preset', name = '')

	def execute(self, context):
		sot = context.scene.sot_props
		name = self.prm_name

		if name == '': return report(self,'Please enter at least something')	

		name = unic_name_geterator(name,pr_values.keys())
		lx,ly,lz,rx,ry,rz = sot.loc_x,sot.loc_y,sot.loc_z, sot.rot_x, sot.rot_y, sot.rot_z
		pr_values[name] = ((round(lx,5),round(ly,5),round(lz,5)),(rx,ry,rz))
		sot.presets = (list(pr_values.keys())[len(pr_values) - 1])

		return{'FINISHED'}

	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self, width=150)

class SOT_OT_Preset_Rem(bpy.types.Operator):
	bl_idname = 'fgt.sot_preset_rem'
	bl_label = 'SOT_OT_Preset_Rem'
	bl_description = 'Remove current item'

	def execute(self, context):
		sot = context.scene.sot_props

		if len(pr_values) != 0:
			if list(pr_values.keys()).index(sot.presets) == len(pr_values) - 1:
				del pr_values[sot.presets]
				if len(pr_values) != 0:
					sot.presets = (list(pr_values.keys())[len(pr_values) - 1])
			else:
				del pr_values[sot.presets]
		else: return report(self,'No more items to remove')
		return{'FINISHED'}

class SOT_OT_Preset_Rrd(bpy.types.Operator):
	bl_idname = 'fgt.sot_preset_rrd'
	bl_label = 'SOT_OT_Preset_Rrd'
	bl_description = 'Reorder item up/down'

	reorder_up: bpr.BoolProperty()

	def execute(self, context):
		global pr_values
		if pr_values == {}: return report(self,"Presets list is EMPTY!!!")
		sot = context.scene.sot_props
		ind = list(pr_values.keys()).index(sot.presets)
		new_pr,ksi,ks = {},[],[]

		if self.reorder_up :
			if ind != 0:
				ksi = [e for e,i in  enumerate(pr_values.keys())]
				ksi[ind] = ksi[ind]-1
				ksi[ind-1] = ksi[ind]+1
				ks = [list(pr_values.keys())[i] for i in ksi]
				for k in ks: new_pr[k] = pr_values.get(k)
				pr_values = new_pr
				sot.presets = ks[ind-1]
			else: return report(self,"Can't move this item UP!!!")
		else:
			if ind != len(pr_values) - 1:
				ksi = [e for e,i in  enumerate(pr_values.keys())]
				ksi[ind] = ksi[ind]+1
				ksi[ind+1] = ksi[ind]-1
				ks = [list(pr_values.keys())[i] for i in ksi]
				for k in ks: new_pr[k] = pr_values.get(k)
				pr_values = new_pr
				sot.presets = ks[ind+1]
			else: return report(self,"Can't move this item DOWN!!!")
		return{'FINISHED'}

class SOT_OT_Preset_Get(bpy.types.Operator):
	bl_idname = 'fgt.sot_preset_get'
	bl_label = 'SOT_OT_Preser_Get'
	bl_description = 'Get value from preset'

	prm_preset_get: bpr.EnumProperty(items= [('loc','Get Location','',1),('rot','Get Rotation','',2),('both','Get Location And Rotation','',3)])


	def execute(self, context):
		sot = context.scene.sot_props

		if pr_values == {}:
			return report(self,"Presets list is EMPTY!!!")
		else:
			if   self.get_preset == 'loc': sot.loc_x,sot.loc_y,sot.loc_z = pr_values.get(sot.presets)[0] 
			elif self.get_preset == 'rot': sot.rot_x, sot.rot_y, sot.rot_z = pr_values.get(sot.presets)[1]
			else:
				sot.loc_x,sot.loc_y,sot.loc_z = pr_values.get(sot.presets)[0] 
				sot.rot_x, sot.rot_y, sot.rot_z = pr_values.get(sot.presets)[1]	

		return{'FINISHED'}



class SOT_OT_Set_Loc_Rot(bpy.types.Operator):
	bl_idname = 'fgt.sot_set_origin_loc_rot'
	bl_label = 'Set Origin Transforms'
	bl_description = 'Set origin location/Orientation'
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
		aob_r = aob
		sob_r = sob
		loc_rot = self.prm_set_loc_rot

		if sot.from_preset and pr_values != {}:
			xl,yl,zl = pr_values.get(sot.presets)[0]
			xr,yr,zr = pr_values.get(sot.presets)[1]
		else:
			xl,yl,zl = self.prm_set_location
			xr,yr,zr = self.prm_set_rotation[:]


		'''
		NOTE
		Зробити щось з анду у випадку з едіт модом
		'''

		eob = object_in_edit(bob,sob_r)

		if self.prm_set_act_bat == '1':
			if aob == None: return report(self,'No ACTIVE object in selection!!!!')
			if loc_rot == 'Loc' or loc_rot == 'Loc + Rot': set_origin_location(xl,yl,zl,aob,bcv)
			if loc_rot == 'Rot' or loc_rot == 'Loc + Rot': set_origin_orientation(xr,yr,zr,aob,bob)
		else:
			if sob_r == []: return report(self,'No SELECTED objects!!!!')
			for tob in sob_r:
				if loc_rot == 'Loc' or loc_rot == 'Loc + Rot': set_origin_location(xl,yl,zl,tob,bcv)
				if loc_rot == 'Rot' or loc_rot == 'Loc + Rot': set_origin_orientation(xr,yr,zr,tob,bob)

		recover_edit(eob,bcv,aob_r,sob_r)

		return {'FINISHED'}	

class SOT_OT_Get_Transform(bpy.types.Operator):
	bl_idname = 'fgt.sot_get_transform'
	bl_label = 'SOT_OT_Get_Transform'
	bl_description = 'Get transform values from...'


	prm_get_transform:	bpr.EnumProperty(items= [('loc_c','Cursor','',1),('loc_a','Active','',2),('rot_c','Cursor','',3),('rot_a','Active','',4)], name= 'Get Transform')

	def execute(self,context):
		sot = context.scene.sot_props
		gtr = self.prm_get_transform
		bco = bpy.context
		bcv = bco.view_layer
		aob = bcv.objects.active

		if gtr == 'loc_c':		#Get location from Cursor
			set_manual_values(sot,get_cursor_loc_rot(bco,sot,True),True)

		elif gtr == 'loc_a':		#Get location from Active Object/Element
			if bco.mode == 'OBJECT':
				value = get_object_loc_rot(self,bco,sot,True)
				if type(value) is not set: set_manual_values(sot,value,True)
			elif bco.mode == 'EDIT_MESH':
				value = get_element_loc(self,bco,sot,aob)
				if type(value) is not set: set_manual_values(sot, value,True)

		elif gtr == 'rot_c':		#Get rotation from Cursor
			set_manual_values(sot, get_cursor_loc_rot(bco,sot,False).to_euler(), False)

		elif gtr == 'rot_a':		#Get rotation from Active Object/Element
			if bco.mode == 'OBJECT':
				value = get_object_loc_rot(self,bco,sot,False)
				if type(value) is not set: set_manual_values(sot, value.to_euler(), False)
			elif bco.mode == 'EDIT_MESH':
				value = get_element_vectors(self,bco,sot,aob)
				if type(value) is not set: set_manual_values(sot, value.to_euler(), False)

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

		if abs(math.degrees(sot.rot_x)) < 0.0001:
			sot.rot_x = 0
		if abs(math.degrees(sot.rot_y)) < 0.0001:
			sot.rot_y = 0
		if abs(math.degrees(sot.rot_z)) < 0.0001:
			sot.rot_z = 0

		return {'FINISHED'}


class SOT_OT_Fixed_Snap(bpy.types.Operator):
	bl_idname = 'fgt.sot_fixed_snap'
	bl_label = 'Set Origin To Fixed Spot'
	bl_description = 'Snap origin position to fixed bounding box point'	
	bl_options = {'REGISTER', 'UNDO'}

	prm_set_spot_a: bpr.EnumProperty(items= [('X','X Axis','',1),('Y','Y Axis','',2),('Z','Z Axis','',3)], name= 'Proojection Along')
	prm_set_spot_b: bpr.EnumProperty(items= [('pos','Positive','',1),('neg','Negative','',2)], name= 'Projection Direction')
	prm_set_spot_c: bpr.EnumProperty(items= [('glb','Global','',1),('loc','Local','',2),('viw','View','',3),('crs','Cursor','',4),('prs','Preset','',5)], name = 'Projection Space')
	prm_set_spot_d: bpr.EnumProperty(items= [
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
		('dtp','Drop To Spot','',13)], name='Choose Spot')

	def execute(self,context):
		bob = bpy.ops.object
		spot = self.prm_set_spot_d
		rep = self.report
		sot = context.scene.sot_props
		bco = bpy.context
		bcv = bco.view_layer
		aob = bcv.objects.active
		sob = bco.selected_objects
		aob_r = aob
		sob_r = sob

		if sot.set_pick == '2':
			if aob_check(aob)[0]: return report(self, aob_check(aob)[1])

			psp = get_snap_spot_active(bco,sot,aob)
			sot.loc_x,sot.loc_y,sot.loc_z = psp.get(spot)
			bpy.ops.ed.undo_push(message = 'Pick Spot Location' )

		else:
			if sot.spots_snap_mode == '1' or sot.batch_spot_mode == '1':

				if aob_check(aob)[0]:  return report(self, aob_check(aob)[1])
				if mesh_check(aob)[0]: return report(self, mesh_check(aob)[1])

				psp = get_snap_spot_active(bco,sot,aob)
				x,y,z = psp.get(spot)


				'''
				NOTE
				анду пуш, покищо хай полежить
				'''

				eob = object_in_edit(bob,sob_r)
				if sot.spots_snap_mode == '1':
					set_origin_location(x,y,z,aob,bcv)
					#bpy.ops.ed.undo_push(message = 'SOT Fixed Snap A')
				elif sot.spots_snap_mode == '2':
					for tob in sob:
						if sot.not_active:
							if tob == aob_r:
								continue
						set_origin_location(x,y,z,tob,bcv)
					#bpy.ops.ed.undo_push(message = 'SOT Fixed Snap BTA')
				recover_edit(eob,bcv,aob_r,sob_r)

			if sot.spots_snap_mode == '2':

				if aob_check(aob)[0]:  return report(self, aob_check(aob)[1])
				for tob in sob:
					if mesh_check(tob)[0]:return report(self, mesh_check(tob)[1])

				eob = object_in_edit(bob,sob_r)
				bpy.ops.ed.undo_push(message = 'SOT Fixed Snap M' )
				recover_edit(eob,bcv,aob_r,sob_r)

			if sot.spots_snap_mode == '3' and sot.batch_spot_mode == '2':

				for tob in sob:
					if mesh_check(tob)[0]:return report(self, mesh_check(tob)[1])

				eob = object_in_edit(bob,sob_r)
				for tob in sob:
					vdt = tob.data.vertices
					obm = tob.matrix_world
					sps = spots(sot,obm,vdt)
					psp = projection(sot,obm,sps)[0]
					psp['dtp'] = projection(sot,obm,sps)[2][1]
					x,y,z = psp.get(spot)
					set_origin_location(x,y,z,tob,bcv)
				bpy.ops.ed.undo_push(message = 'SOT Fixed Snap BPO' )
				recover_edit(eob,bcv,aob_r,sob_r)

		return{'FINISHED'}

class SOT_OT_Clear_Value(bpy.types.Operator):
	bl_idname = 'fgt.sot_clear_value'
	bl_label = 'SOT_OT_Clear_Value'

	cop: bpr.StringProperty(name = '', default = '')
	cln_dic = {'loc':'= 0','rot':'= 0','z_a':"= 'z+'",'rem':"= '1'",'off':'= 0','spo':'= 1'}

	def execute(self,context):
		sot = context.scene.sot_props
		exec('sot.'+ self.cop + self.cln_dic.get(self.cop[0:3]))
		bpy.ops.ed.undo_push(message = 'SOT Clear Value' )
		return {'FINISHED'}

class SOT_OT_Draw_Axis(bpy.types.Operator):
	bl_idname = 'fgt.sot_draw_axis'
	bl_label = 'SOT_OT_Draw_Axis'

	def modal(self,context,event):

		sot = context.scene.sot_props
	
		if not sot.draw_axis:
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
			return {'CANCELLED'}

		try:
			context.area.tag_redraw()
		except:
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
			sot.draw_axis = False
			return {'CANCELLED'}
		else:
			context.area.tag_redraw()
			return {'PASS_THROUGH'}

	def invoke(self,context,event):
		for area in bpy.context.window.screen.areas:
			if area.type == 'VIEW_3D':
				args = (self,context)
				self.draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_axis_main, args, 'WINDOW', 'POST_VIEW')
				context.window_manager.modal_handler_add(self)
				return {'RUNNING_MODAL'}

class SOT_OT_Draw_Spots(bpy.types.Operator):
	bl_idname = 'fgt.sot_draw_spots'
	bl_label = 'SOT_OT_Draw_Spots'

	def modal(self,context,event):
		sot = context.scene.sot_props
	
		if not sot.draw_spots:
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
			sot.manual_recalc = False
			return {'CANCELLED'}

		try:
			context.area.tag_redraw()
		except:
			bpy.types.SpaceView3D.draw_handler_remove(self.draw_handler, 'WINDOW')
			sot.manual_recalc = False
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

class SOT_PR_Settings_Props(bpy.types.PropertyGroup):

	loc_x: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)
	loc_y: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)
	loc_z: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)

	rot_x: bpr.FloatProperty(subtype = 'ANGLE', min= -6.28319, max= 6.28319)
	rot_y: bpr.FloatProperty(subtype = 'ANGLE', min= -6.28319, max= 6.28319)
	rot_z: bpr.FloatProperty(subtype = 'ANGLE', min= -6.28319, max= 6.28319)

	z_axis: bpr.EnumProperty(name='',
		items= [('z+','Z+ Same','Z+ axis untached as it is.',1),
				('z-','Z- Axis','Z+ use Z- vector',2),
				('y+','Y+ Axis','Z+ use Y+ vector',3),
				('y-','Y- Axis','Z+ use Y+ vector',4),
				('x+','X+ Axis','Z+ use X+ vector',5),
				('x-','X- Axis','Z+ use X+ vector',6)], default= 'z+')

	presets: bpr.EnumProperty(
		items = enum_update_presets, name = 'Loc/Orient Presets', description = 'Preset')

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

	set_spot_axis: bpr.EnumProperty(items= [('1','X','',1),('2','Y','',2),('3','Z','',3)], default= '1')
	set_spot_dir: bpr.EnumProperty(items= [('1','Positive','',1),('2','Negative','',2)], default= '1')
	set_spot_space: bpr.EnumProperty(items= [('1','Global','',1),('2','Local','',2),('3','View','',3),('4','Cursor','',4),('5','Custom','',5)])

	from_preset: bpr.BoolProperty(name = '', default = False)

	draw_axis: bpr.BoolProperty(name = '', default = False, update= prop_update_draw_axis)

	set_pick: bpr.EnumProperty(
		items= [('1','Set Origin','Set ORIGIN location to FIXED spot',1),
				('2','Pick Spot','Pick ACTIVE object spot LOCATION values',2)], default= '1', update= prop_update_set_pick)

	spots_snap_mode: bpr.EnumProperty(
		items= [('1','Active','Set ORIGIN for ACTIVE object only',1),
				('2','Multi','Set ORIGINS for MULTIPLE objects as if they are single object',2),
				('3','To Active','Set ORIGINS of MULTIPLE objects to ACTIVE object spots',3),
				('4','For Each','Set ORIGINS for EACH object own spots in selection',4)], default= '1')

	not_active: bpr.BoolProperty(name = '', default = False)

	active_batch: bpr.EnumProperty(
		items= [('1','Active','Set ORIGIN for ACTIVE object only',1),
				('2','Batch','Set ORIGIN for EACH object in selection',2)], default= '1')

	manual_recalc: bpr.BoolProperty(
		name = '', default = True, update= prop_update_manual_recalc,
		description = 'Recalculate current mesh bound spots manually')





	drop_to_mode: bpr.EnumProperty(
		items= [('1','Space','Drop ORIGIN to current SPACE',1),
				('2','Bound','Drop ORIGIN to current BOUND in current space',2)], default= '1')

	drop_to_space_sub: bpr.EnumProperty(
		items= [('1','Zero','Drop ORIGIN to selected SPACE zero',1),
				('2','Median','Drop ORIGIN to MEDIAN between selected objects (designed for multiple objects)',2)], default= '1')

	drop_to_bound_sub: bpr.EnumProperty(
		items= [('1','Side','Drop ORIGIN to bound SIDE',1),
				('2','Median','Drop ORIGIN to bound MEDAIN',2)], default= '1')

	drop_to_offset: bpr.FloatProperty(subtype = 'DISTANCE', precision= 6)

	draw_spots: bpr.BoolProperty(name = '', default = False, update= prop_update_draw_spots)
	spots_auto: bpr.EnumProperty(
		items= [('1','Auto','Auto bound spots recalculation (may cause low performance on high poly mesh!!!)',1),
				('2','Manual','Manual bound spots recalculation',2)], default= '2')
	spots_scale: bpr.FloatProperty(default= 1,precision= 2,min= 0.1, max= 2)

	# TO REMOVE -----------------------------------------------------------------------

	active_batch_spot: bpr.EnumProperty(
		items= [('1','Active','Set ORIGIN for ACTIVE object only',1),			
				('2','Batch','Set ORIGIN for EACH object in selection',2)], default= '1')

	batch_spot_mode: bpr.EnumProperty(
		items= [('1','To Active','Set ORIGINS to ACTIVE object spot',1),
				('2','Multi','Set ORIGIN for ALL objects in selection',2),
				('3','For Eac','Set ORIGINS for EACH object own spot',3)], default= '1')

ctr = [
	SOT_PT_Panel,
	SOT_PT_Location_Orientation,
	SOT_PT_Presets,
	SOT_PT_Location,
	SOT_PT_Orientation,
	SOT_PT_Fixed_Snap,
	SOT_OT_Preset_Ren,
	SOT_OT_Preset_Add,
	SOT_OT_Preset_Rem,
	SOT_OT_Preset_Rrd,
	SOT_OT_Preset_Get,
	SOT_OT_Set_Loc_Rot,
	#SOT_OT_Set_Location,
	#SOT_OT_Set_Orientation,
	SOT_OT_Get_Transform,
	SOT_OT_Rotate_Ninety,
	SOT_OT_Fixed_Snap,
	SOT_OT_Clear_Value,
	SOT_OT_Draw_Axis,
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
