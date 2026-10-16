"""Reproducible local body clearance repair; no trajectory or wheel changes.

The input file records the assumed geometry and authoritative contact inputs.
If those change, fail explicitly rather than silently reusing a stale envelope.
"""
from pathlib import Path
import bisect,json,hashlib,math
import bpy,bmesh

def apply_clearance_adjustment(root,objects,parameters):
    path=root/'Data/vehicle_clearance_adjustment.json'
    if not path.exists():raise RuntimeError('Missing required Data/vehicle_clearance_adjustment.json')
    config=json.loads(path.read_text(encoding='utf-8'))
    if not config.get('enabled'):return {'enabled':False,'config_file':'Data/vehicle_clearance_adjustment.json'}
    for name,expected in config['nominal_input_parameters'].items():
        if abs(float(parameters[name])-expected)>1e-6:raise RuntimeError('Clearance envelope requires recomputation after changing '+name)
    for name,key in [('Data/trajectory_fit.csv','trajectory_sha256'),('Data/ramp_dense.json','ramp_dense_sha256')]:
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=config[key]:raise RuntimeError('Stale clearance envelope: '+name+' changed; recompute and validate before building')
    xs=config['local_x_cm'];zs=config['minimum_local_z_cm_with_1cm_margin']
    if len(xs)!=len(zs) or any(b<=a for a,b in zip(xs,xs[1:])):raise RuntimeError('Invalid clearance envelope profile')
    def floor(x):
        if x<xs[0] or x>xs[-1]:raise RuntimeError('Body vertex outside clearance profile')
        i=max(0,min(len(xs)-2,bisect.bisect_right(xs,x)-1));a=(x-xs[i])/(xs[i+1]-xs[i])
        return zs[i]*(1-a)+zs[i+1]*a
    anchor=config['outer_overhang_anchor_cm'];ratio=(config['nominal_tip_after_cm']-anchor)/(config['nominal_tip_before_cm']-anchor)
    deps=bpy.context.evaluated_depsgraph_get();prepared=[]
    rigid_rear=0.;rigid_lip=0.;rigid_plate=0.
    for obj in objects:
        if obj.type!='MESH':continue
        mesh=bpy.data.meshes.new_from_object(obj.evaluated_get(deps),preserve_all_data_layers=True,depsgraph=deps)
        world=[obj.matrix_world@v.co for v in mesh.vertices];new=[p.copy() for p in world]
        for p in new:
            if abs(p.x)>anchor:p.x=math.copysign(anchor+(abs(p.x)-anchor)*ratio,p.x)
        need=[max(0.,floor(p.x)-p.z) for p in new]
        required=max(need,default=0.)
        rear=obj.name.startswith('Rear_Visible_Circular_Aperture_') or obj.name.startswith('Rear_Diffuser_')
        if rear:rigid_rear=max(rigid_rear,required)
        if obj.name=='Front_Lower_Lip':rigid_lip=required
        if obj.name=='Rear_Plate_RDSTR':rigid_plate=required
        prepared.append((obj,mesh,world,new,need,rear))
    changes={};all_deltas=[]
    for obj,mesh,old,new,need,rear in prepared:
        rigid=rigid_rear if rear else rigid_lip if obj.name=='Front_Lower_Lip' else rigid_plate if obj.name=='Rear_Plate_RDSTR' else None
        for p,d in zip(new,need):p.z+=d if rigid is None else rigid
        delta=[b-a for a,b in zip(old,new)]
        max_x=max((abs(d.x) for d in delta),default=0.);max_z=max((d.z for d in delta),default=0.)
        if max_x>1e-6 or max_z>1e-6:changes[obj.name]={'max_abs_x_change_cm':max_x,'max_local_z_raise_cm':max_z,'rigid_z_translation':rigid is not None}
        inv=obj.matrix_world.inverted()
        for vertex,p in zip(mesh.vertices,new):vertex.co=inv@p
        # Cleanup only collapsed microscopic edges introduced by bottom reshaping.
        bm=bmesh.new();bm.from_mesh(mesh)
        bmesh.ops.dissolve_degenerate(bm,dist=1e-7,edges=list(bm.edges))
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        obj.modifiers.clear();obj.data=mesh;mesh.update();all_deltas.extend(delta)
    return {'enabled':True,'status':config['status'],'config_file':'Data/vehicle_clearance_adjustment.json','config_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'nominal_parameters_meaning':'design inputs before local overhang/body-floor repair; actual final dimensions are measured vehicle_bounds_cm',
        'anchor_cm':anchor,'nominal_tip_before_cm':config['nominal_tip_before_cm'],'nominal_tip_after_cm':config['nominal_tip_after_cm'],
        'rear_circle_and_diffuser_rigid_z_shift_cm':rigid_rear,'front_lip_rigid_z_shift_cm':rigid_lip,'plate_rigid_z_shift_cm':rigid_plate,
        'changed_objects':changes,'max_body_vertex_z_raise_cm':max((d.z for d in all_deltas),default=0.),
        'unchanged':'wheel meshes/centers/radius, wheelbase, high canopy, trajectory and ramp',
        'not_measured':'No claim that shortened body dimensions or reshaped underside are official Tesla geometry'}
