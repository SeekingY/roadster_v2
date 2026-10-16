"""Encode an explicit, complete, fresh MRQ run without retiming or registration.
Run: python encode_deliverables.py --source 4k --include-inspection
Requires the completed Run.ps1 receipt, or an explicit completed native UE log.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, os, re, shutil, struct, subprocess

ROOT=Path(__file__).resolve().parents[1]
FF=os.environ.get('FFMPEG_EXE') or shutil.which('ffmpeg')
if not FF:
    raise RuntimeError('Install FFmpeg separately and put it on PATH or set FFMPEG_EXE. No third-party binary is bundled.')
OUT=ROOT/'Renders'
FPS='24000/1001'
N=419
JOBS={'4k':('reference_4k','Ramp_Final_4K',(3840,2160)),
      '1080':('reference_1080','Ramp_Final_1080',(1920,1080)),
      'inspection':('inspection','Ramp_Inspection_720',(1280,720))}

def run(args):
    result=subprocess.run([str(FF),'-hide_banner','-loglevel','warning','-xerror','-y',
        *map(str,args)],text=True,capture_output=True,encoding='utf-8',errors='replace')
    if result.returncode:
        raise RuntimeError(f'FFmpeg failed with code{result.returncode}: '+result.stderr[-6000:])
    return result.stdout

def utc_timestamp(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()

def gate_render(mode, explicit_log=None):
    folder,preset,size=JOBS[mode]
    manifest=ROOT/'Validation/build_manifest.json'
    if not manifest.exists():
        manifest=ROOT/'PUBLICATION_MANIFEST.json'
    if not manifest.exists():
        raise RuntimeError('Missing build/publication manifest; cannot distinguish stale frames')
    if explicit_log:
        path=Path(explicit_log).resolve()
        text=path.read_text(encoding='utf-8-sig',errors='replace')
        if '/Game/Render/'+preset+'.'+preset not in text:
            raise RuntimeError('Render log does not identify requested preset: '+preset)
        if 'MoviePipelineLinearExecutorBase finished 1 jobs' not in text or 'LogExit: Exiting.' not in text:
            raise RuntimeError('Render log lacks completed pipeline and editor shutdown evidence')
        stamp=re.search(r'\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3})\]',text)
        if not stamp:
            raise RuntimeError('No native UTC timestamp found in render log')
        start=datetime.strptime(stamp.group(1),'%Y.%m.%d-%H.%M.%S:%f').replace(tzinfo=timezone.utc).timestamp()
        receipt=dict(method='explicit completed native UE log',file=str(path),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),render_start_timestamp=start)
    else:
        path=ROOT/'Validation'/('render_receipt_'+preset+'.json')
        if not path.exists():
            raise RuntimeError('Missing render receipt; use Run.ps1 or provide this run completed UE log: '+str(path))
        receipt=json.loads(path.read_text(encoding='utf-8-sig'))
        if receipt.get('preset')!=preset or receipt.get('exit_code')!=0 or receipt.get('status')!='process_completed_pending_frame_validation':
            raise RuntimeError('Requested render run has not completed successfully: '+str(path))
        start=utc_timestamp(receipt['render_start_utc'])
    floor=max(start,manifest.stat().st_mtime)
    expected=[OUT/folder/(preset+'.%04d.png'%f) for f in range(N)]
    actual=set((OUT/folder).glob(preset+'.*.png'))
    if actual!=set(expected):
        missing=[p.name for p in expected if p not in actual]
        extra=[p.name for p in actual if p not in expected]
        raise RuntimeError(f'{mode}: require exactly frames0000..0418; missing={missing[:8]}, extra={extra[:8]}')
    stamps=[]
    for p in expected:
        stat=p.stat()
        if stat.st_mtime<floor:
            raise RuntimeError('Stale frame predates current render run or last build: '+str(p))
        with p.open('rb') as stream:
            header=stream.read(24)
        if len(header)!=24 or header[:8]!=b'\x89PNG\r\n\x1a\n' or header[12:16]!=b'IHDR':
            raise RuntimeError('Invalid PNG header: '+str(p))
        if struct.unpack('>II',header[16:24])!=size:
            raise RuntimeError('Unexpected frame dimensions: '+str(p))
        stamps.append((stat.st_size,stat.st_mtime_ns))
    return dict(mode=mode,folder=folder,prefix=preset,size=size,receipt=receipt,
        build_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
        freshness_floor_utc=datetime.fromtimestamp(floor,timezone.utc).isoformat(),
        first_frame_mtime_utc=datetime.fromtimestamp(expected[0].stat().st_mtime,timezone.utc).isoformat(),
        last_frame_mtime_utc=datetime.fromtimestamp(expected[-1].stat().st_mtime,timezone.utc).isoformat(),
        expected=expected,stamps=stamps)

def assert_unchanged(job):
    for p,old in zip(job['expected'],job['stamps']):
        current=p.stat()
        if (current.st_size,current.st_mtime_ns)!=old:
            raise RuntimeError('Render input changed during encoding: '+str(p))

def decoded_frame_count(path):
    progress=run(['-i',path,'-map','0:v:0','-an','-progress','pipe:1','-f','null','-'])
    counts=re.findall(r'^frame=(\d+)\s*$',progress,re.M)
    if not counts or int(counts[-1])!=N:
        raise RuntimeError('Encoded output did not decode to exactly419 frames: '+str(path))
    return int(counts[-1])

def encode(job,dest,width=None):
    target=OUT/dest
    temporary=target.with_name(target.stem+'.encoding.mp4')
    args=['-framerate',FPS,'-start_number','0','-i',
        OUT/job['folder']/(job['prefix']+'.%04d.png'),'-frames:v',N]
    if width:
        args+=['-vf',f'scale={width}:-2:flags=lanczos']
    args+=['-an','-c:v','libx264','-threads','4','-preset','medium','-crf','18',
        '-pix_fmt','yuv420p','-video_track_timescale','24000','-movflags','+faststart',temporary]
    run(args)
    assert_unchanged(job)
    decoded_frame_count(temporary)
    temporary.replace(target)
    return target

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=['4k','1080'],required=True)
    parser.add_argument('--include-inspection',action='store_true')
    parser.add_argument('--reference-render-log',type=Path)
    parser.add_argument('--inspection-render-log',type=Path)
    args=parser.parse_args()
    reference=gate_render(args.source,args.reference_render_log)
    inspection=gate_render('inspection',args.inspection_render_log) if args.include_inspection else None
    report=dict(status='encoding_in_progress',source_mode=args.source,frames=N,
        frame_rate=[24000,1001],duration_s=N*1001/24000,source_interval_frames=[0,418],
        created_utc=datetime.now(timezone.utc).isoformat(),
        audio='silent; no synthetic audio passed off as source',
        validation='all419 expected PNG names, dimensions, run/build timestamps; strict FFmpeg decode; no inputs changed while encoding',
        inputs=[{k:v for k,v in j.items() if k not in ['expected','stamps']} for j in [reference,inspection] if j],outputs=[])
    report_path=ROOT/'Validation/video_outputs.json'
    def write():
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def record(path):
        report['outputs'].append(dict(file=str(path.relative_to(ROOT)),bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),decoded_frames=N))
    write()
    try:
        if args.source=='4k':
            record(encode(reference,'Reference_Replay_4K.mp4'))
            record(encode(reference,'Reference_Replay_1080.mp4',1920))
        else:
            record(encode(reference,'Reference_Replay_1080.mp4'))
        if inspection:
            record(encode(inspection,'Inspection_3D.mp4'))
        assert_unchanged(reference)
        if inspection:
            assert_unchanged(inspection)
        report['status']='encoded_and_decoded_all_requested_outputs'
        report['completed_utc']=datetime.now(timezone.utc).isoformat()
        write()
        print(json.dumps(report,ensure_ascii=False,indent=2))
    except Exception as exc:
        report['status']='failed';report['error']=repr(exc);write()
        raise

if __name__=='__main__':
    main()
