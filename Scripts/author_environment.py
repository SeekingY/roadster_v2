"""Visible ground fixtures placed by ray/assumed-ground intersections.

Only visible image positions constrain these details, not their real depths,
sizes, illumination or engineering. No image plane or reference texture.
"""
import unreal,math,json,os
from unreal_helpers import *

def add_visible_ground_details(root):
    keys=json.load(open(os.path.join(root,'Data','camera_fit_keys.json')))['camera_keys']
    k=next(k for k in keys if k['source_frame']==264)
    c=k['unreal_location_cm']; r=k['unreal_rotation_deg']
    pitch,yaw=math.radians(r['pitch']),math.radians(r['yaw'])
    cp,sp,cy,sy=math.cos(pitch),math.sin(pitch),math.cos(yaw),math.sin(yaw)
    f=[cp*cy,cp*sy,sp];right=[-sy,cy,0];up=[-sp*cy,-sp*sy,cp]
    focal=k['focal_length_mm']/36*1920
    def world(px,py,z=4):
        ray=[f[i]+(px-960)/focal*right[i]-(py-540)/focal*up[i] for i in range(3)]
        assert ray[2]<0,'Ground ray must point below horizon'
        t=(z-c[2])/ray[2]
        return [c[i]+t*ray[i] for i in range(3)]
    cube=unreal.load_asset('/Engine/BasicShapes/Cube')
    sphere=unreal.load_asset('/Engine/BasicShapes/Sphere')
    red=material('M_ObservedGroundRedV2',(.85,.001,.003),0,.5,18)
    white=material('M_ObservedFixtureWhite',(.75,.88,1.0),0,.4,12)
    dark=material('M_FixtureHousing',(.004,.006,.009),0,.7)
    line_pixels=[[238,1010],[1004,1010]]
    ends=[world(*p) for p in line_pixels]
    beam('Observed_Red_Ground_Strip_estimated_depth',ends[0],ends[1],8,red,cube)
    # Visible low white lamps in the official source. Clusters remain sparse;
    # there is no invented crowd geometry or smoke hiding contact errors.
    pixels=[[194,984],[215,982],[240,978],[266,973],[292,968.5],[318,968.5],
            [341,971],[364,975],[387,981],[410,986],[433,989],[863,986],[878,986],[893,987],
            [987,1000],[1033,1002],[1076,1004],[1128,1003],[1180,1001],[1230,1000]]
    fixtures=[]
    for i,(px,py) in enumerate(pixels):
        try:loc=world(px,py,8)
        except AssertionError:continue
        distance=math.dist(loc,c)
        if distance>40000:continue
        size=max(3,min(60,distance/focal*4))
        a=mesh_actor('Observed_Fixture_%02d_estimated_depth'%i,sphere,loc,scale=(size/100,size/100,size/100),mat=white)
        a.static_mesh_component.set_editor_property('cast_shadow',False)
        mesh_actor('Fixture_Housing_%02d'%i,cube,(loc[0],loc[1],loc[2]-size*.25),scale=(size*.018,size*.018,size*.006),mat=dark)
        fixtures.append({'source_pixel':[px,py],'assumed_world_cm':loc,'assumed_diameter_cm':size})
    json.dump({'status':'appearance-only estimate; no metric recovery of stage equipment',
        'source':'research/ramp_source_1080/frame_00000264.png','source_frame':264,
        'method':'inverse pinhole rays intersect assumed ground height; single-frame positions only',
        'red_strip_source_pixels':line_pixels,'red_strip_assumed_world_cm':ends,
        'fixtures':fixtures,'limits':['depth and scale depend on unverified camera height',
        'lamp intensities, sizes and housing shapes are approximations','no independent reprojection validation',
        'ambient illumination and concrete material not photometrically calibrated']},
        open(os.path.join(root,'Data','environment_appearance_assumptions.json'),'w'),indent=2)
