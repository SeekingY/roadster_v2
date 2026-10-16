"""Procedural surface detail and time-addressable visible-gas approximation.
Not nozzle layout evidence or fluid simulation. No Time node or stateful particles.
"""
import unreal,math,json,os,random
from unreal_helpers import *
MEL=unreal.MaterialEditingLibrary
def scalar(mat,value):
    e=MEL.create_material_expression(mat,unreal.MaterialExpressionConstant);e.set_editor_property('r',value);return e
def color(mat,value):
    e=MEL.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector);e.set_editor_property('constant',unreal.LinearColor(*value,1));return e
def connect(a,b,pin='A'):MEL.connect_material_expressions(a,'',b,pin)
def surface_detail():
    m=load_if('/Game/Materials/M_RampSurface')
    MEL.delete_all_material_expressions(m)
    n=MEL.create_material_expression(m,unreal.MaterialExpressionNoise)
    n.set_editor_property('scale',.035);n.set_editor_property('quality',1);n.set_editor_property('levels',3)
    n.set_editor_property('output_min',.92);n.set_editor_property('output_max',1.03)
    mul=MEL.create_material_expression(m,unreal.MaterialExpressionMultiply);connect(color(m,(.18,.195,.20)),mul);connect(n,mul,'B')
    MEL.connect_material_property(mul,'',unreal.MaterialProperty.MP_BASE_COLOR)
    MEL.connect_material_property(scalar(m,.86),'',unreal.MaterialProperty.MP_ROUGHNESS)
    MEL.connect_material_property(scalar(m,.04),'',unreal.MaterialProperty.MP_METALLIC)
    MEL.recompile_material(m);EAL.save_loaded_asset(m)
    # Lower red emissive intensity avoids orange clipping.
    for path in ['/Game/Materials/M_RampEdge','/Game/Materials/M_RedTail']:
        mat=load_if(path)
        if mat:
            MEL.delete_all_material_expressions(mat)
            c=color(mat,(.7,.001,.002));MEL.connect_material_property(c,'',unreal.MaterialProperty.MP_BASE_COLOR)
            MEL.connect_material_property(c,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
            MEL.connect_material_property(scalar(mat,.45),'',unreal.MaterialProperty.MP_ROUGHNESS)
            MEL.recompile_material(mat);EAL.save_loaded_asset(mat)
def gas_material():
    path='/Game/Materials/M_VisibleGas_Approximation';m=load_if(path)
    if not m:m=ASSETS.create_asset('M_VisibleGas_Approximation','/Game/Materials',unreal.Material,unreal.MaterialFactoryNew())
    MEL.delete_all_material_expressions(m)
    m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_TRANSLUCENT);m.set_editor_property('two_sided',True)
    m.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
    MEL.connect_material_property(color(m,(.15,.29,.34)),'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    fr=MEL.create_material_expression(m,unreal.MaterialExpressionFresnel);fr.set_editor_property('exponent',1.0);fr.set_editor_property('base_reflect_fraction',0.0)
    inv=MEL.create_material_expression(m,unreal.MaterialExpressionOneMinus);connect(fr,inv,'')
    noise=MEL.create_material_expression(m,unreal.MaterialExpressionNoise);noise.set_editor_property('scale',.12);noise.set_editor_property('levels',2);noise.set_editor_property('quality',1);noise.set_editor_property('output_min',.05);noise.set_editor_property('output_max',.45)
    mul=MEL.create_material_expression(m,unreal.MaterialExpressionMultiply);connect(inv,mul);connect(noise,mul,'B')
    MEL.connect_material_property(mul,'',unreal.MaterialProperty.MP_OPACITY)
    MEL.recompile_material(m);EAL.save_loaded_asset(m);return m
def add_visible_gas(seq,body,rows,root):
    mat=gas_material();sphere=unreal.load_asset('/Engine/BasicShapes/Sphere');frames=[int(r['frame']) for r in rows]
    rng=random.Random(5715)
    # Four geometric anchors are an explicit approximation; only visible stream appearance is evidence.
    anchors=[(-135,-72,18),(-135,72,18),(135,-72,18),(135,72,18)]
    for j,(x,y,z) in enumerate(anchors):
        for k in range(10):
            phase=rng.random()*math.tau;length=25+k*47;radius=5+k*2.9
            a=mesh_actor('Gas_Approx_%d_%02d'%(j,k),sphere,(x,y,z-length),mat=mat)
            a.static_mesh_component.set_editor_property('cast_shadow',False)
            a.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            a.attach_to_actor(body,'',unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,unreal.AttachmentRule.KEEP_RELATIVE,False)
            values=[]
            for r in rows:
                t=float(r['source_clip_time_s']);on=max(0,min(1,(t-10.55)/.35,(13.3-t)/.7))
                sway=math.sin(phase+t*3+k*.4)*radius*.3
                values.append([x+sway,y+sway*.6,z-length,0,0,0,max(.0001,radius/50*on),max(.0001,radius/50*on),max(.0001,.8*on)])
            transform_track(seq,a,frames,values)
    json.dump({'status':'appearance hypothesis only; not measured nozzle positions or fluid dynamics','source_visible':'blue-white downward streams during upright descent; no flame','anchors_body_cm':anchors,'anchor_count_status':'assumed four-corner layout, not recovered hardware','active_s':[10.55,13.3],'time_status':'coarse visible interval approximation, not one-frame event certification','cache_policy':'deterministic saved transform keys, procedural WorldPosition noise; no Time expression or runtime particle history','landing_cloud':'omitted so it cannot conceal contact uncertainty or fitting errors'},open(os.path.join(root,'Data','gas_appearance_assumptions.json'),'w'),indent=2)
