"""Inverse-dynamics diagnostics for a stated motion hypothesis, not a physics solve.

Reads a frozen snapshot of trajectory_initial.csv; never edits it or injects forces.
Requires only the Python standard library. Rerun after trajectory changes.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, bisect, csv, hashlib, io, json, math

ROOT = Path(__file__).resolve().parents[1]
G = (0.0, 0.0, -9.80665)
MASSES = (1500, 2000, 2500)
STEPS = (1/24, 1/48)
CONTACT_PHASES = {'ramp_contact_hypothesis', 'contact_or_partial_release_estimate'}

def norm(v):
    return math.sqrt(sum(x*x for x in v))

def dot(a,b):
    return sum(x*y for x,y in zip(a,b))

def csv_write(path, rows):
    if not rows:
        return
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

def sample(t, times, rows):
    i=max(0,min(len(rows)-2,bisect.bisect_right(times,t)-1))
    u=(t-times[i])/(times[i+1]-times[i])
    xyz=[(rows[i][k]*(1-u)+rows[i+1][k]*u)/100 for k in ('x_cm','y_cm','z_cm')]
    angles=[rows[i][k]*(1-u)+rows[i+1][k]*u for k in
            ('roll_deg_unwrapped','pitch_deg_unwrapped','yaw_deg_unwrapped')]
    phase=rows[i]['phase'] if t<times[i+1] else rows[i+1]['phase']
    return xyz,angles,phase

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trajectory',type=Path,default=ROOT/'Data/trajectory_fit.csv')
    args=parser.parse_args()
    source=args.trajectory.resolve()
    snapshot=source.read_bytes()
    raw=list(csv.DictReader(io.StringIO(snapshot.decode('utf-8-sig'))))
    numeric=('source_clip_time_s','x_cm','y_cm','z_cm','roll_deg_unwrapped',
             'pitch_deg_unwrapped','yaw_deg_unwrapped')
    if len(raw)<5:
        raise ValueError('At least five trajectory samples are required')
    for row in raw:
        for field in numeric:
            row[field]=float(row[field])
            if not math.isfinite(row[field]):
                raise ValueError('Non-finite trajectory input: '+field)
        row['phase']=row.get('phase','unknown')
    times=[r['source_clip_time_s'] for r in raw]
    if any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('Input timestamps must be strictly increasing')
    # Source editing boundaries are not continuous-time physics observations.
    # Retain the raw derivative, but identify every stencil whose linear native
    # input support overlaps the last-frame to next-shot interval.
    cut_intervals=[]
    shot_path=ROOT/'Data/shot_list.csv'
    if shot_path.exists():
        for shot in csv.DictReader(shot_path.open(encoding='utf-8-sig')):
            try:
                left,right=float(shot['last_pts_s']),float(shot['next_cut_pts_s'])
            except (ValueError,KeyError):
                continue
            if times[0] <= left < right <= times[-1]:
                cut_intervals.append([left,right])
    data=ROOT/'Data'; validation=ROOT/'Validation'
    data.mkdir(exist_ok=True); validation.mkdir(exist_ok=True)
    positions=[[r[k]/100 for k in ('x_cm','y_cm','z_cm')] for r in raw]
    slopes=[[(positions[i+1][j]-positions[i][j])/(times[i+1]-times[i]) for j in range(3)]
            for i in range(len(raw)-1)]
    corners=[]
    for i in range(1,len(raw)-1):
        jump=[slopes[i][j]-slopes[i-1][j] for j in range(3)]
        if norm(jump)>1e-6:
            corners.append(dict(source_row=i,source_time_s=times[i],phase=raw[i]['phase'],
                delta_v_x_m_s=jump[0],delta_v_y_m_s=jump[1],delta_v_z_m_s=jump[2],
                delta_v_norm_m_s=norm(jump),
                meaning='velocity jump of linear interpolant; distributional impulse per kg; not measured vehicle acceleration'))
    csv_write(data/'physics_linear_corners.csv',corners)
    results=[]; mass_rows=[]
    for dt in STEPS:
        label=f'{round(1/dt):02d}hz'
        ts=[times[0]+k*dt for k in range(math.floor((times[-1]-times[0])/dt)+1)]
        samples=[sample(t,times,raw) for t in ts]
        records=[]
        for i in range(1,len(samples)-1):
            p,angles,phase=samples[i]
            velocity=[(samples[i+1][0][j]-samples[i-1][0][j])/(2*dt) for j in range(3)]
            accel=[(samples[i+1][0][j]-2*p[j]+samples[i-1][0][j])/(dt*dt) for j in range(3)]
            specific_force=[accel[j]-G[j] for j in range(3)]
            transition=samples[i-1][2]!=phase or samples[i+1][2]!=phase
            cut_crossing=any(ts[i]-dt<right and ts[i]+dt>left for left,right in cut_intervals)
            contact=phase in CONTACT_PHASES
            roll,pitch,yaw=angles
            valid_normal=contact and abs(roll)<1e-3
            normal=None
            required_normal=None
            adhesion=None
            inverted=None
            if valid_normal:
                p_rad,y_rad=math.radians(pitch),math.radians(yaw)
                # Surface-to-car outward normal for unbanked ramp contact.
                # This is a ramp-normal hypothesis, not a measured collision normal.
                normal=(-math.sin(p_rad)*math.cos(y_rad),-math.sin(p_rad)*math.sin(y_rad),math.cos(p_rad))
                required_normal=dot(specific_force,normal)
                adhesion=max(0,-required_normal)
                inverted=normal[2]<0
            r=dict(sample_time_s=ts[i],step_s=dt,phase=phase,
              x_m=p[0],y_m=p[1],z_m=p[2],
              vx_m_s=velocity[0],vy_m_s=velocity[1],vz_m_s=velocity[2],speed_m_s=norm(velocity),
              ax_m_s2=accel[0],ay_m_s2=accel[1],az_m_s2=accel[2],acceleration_norm_m_s2=norm(accel),
              nongravity_fx_per_kg=specific_force[0],nongravity_fy_per_kg=specific_force[1],
              nongravity_fz_per_kg=specific_force[2],nongravity_force_norm_per_kg=norm(specific_force),
              ramp_normal_x=normal[0] if normal else '',ramp_normal_y=normal[1] if normal else '',
              ramp_normal_z=normal[2] if normal else '',
              required_normal_force_per_kg=required_normal if required_normal is not None else '',
              inward_force_requirement_per_kg=adhesion if adhesion is not None else '',
              ramp_inverted=inverted if inverted is not None else '',
              derivative_crosses_phase_boundary=transition,
              derivative_support_crosses_source_edit=cut_crossing,
              interpretation='hypothesis inverse dynamics; not measured force or Chaos result')
            records.append(r)
        csv_write(data/f'physics_timeseries_{label}.csv',records)
        inverted_records=[r for r in records if r['ramp_inverted'] is True]
        positive_inward=[r for r in inverted_records if r['inward_force_requirement_per_kg']>1e-8]
        phase_stats={}
        for phase in sorted({r['phase'] for r in records}):
            subset=[r for r in records if r['phase']==phase]
            max_acc=max(subset,key=lambda r:r['acceleration_norm_m_s2'])
            max_force=max(subset,key=lambda r:r['nongravity_force_norm_per_kg'])
            phase_stats[phase]=dict(sample_count=len(subset),
                max_acceleration_m_s2=max_acc['acceleration_norm_m_s2'],max_acceleration_time_s=max_acc['sample_time_s'],
                max_nongravity_force_per_kg=max_force['nongravity_force_norm_per_kg'],
                max_nongravity_force_time_s=max_force['sample_time_s'])
            for mass in MASSES:
                mass_rows.append(dict(step_s=dt,phase=phase,mass_kg=mass,
                  mass_status='exploratory assumption; not official vehicle mass',
                  max_nongravity_resultant_N=mass*max_force['nongravity_force_norm_per_kg'],
                  max_nongravity_resultant_time_s=max_force['sample_time_s'],
                  static_weight_N=mass*abs(G[2]),
                  status='necessary resultant for chosen kinematics, not actuator verification'))
        maximum=max(records,key=lambda r:r['acceleration_norm_m_s2'])
        maximum_force=max(records,key=lambda r:r['nongravity_force_norm_per_kg'])
        maximum_inward=max(positive_inward,key=lambda r:r['inward_force_requirement_per_kg']) if positive_inward else None
        result=dict(label=label,step_s=dt,interior_sample_count=len(records),
          peak_acceleration_m_s2=maximum['acceleration_norm_m_s2'],peak_acceleration_time_s=maximum['sample_time_s'],
          peak_nongravity_force_per_kg=maximum_force['nongravity_force_norm_per_kg'],
          peak_nongravity_force_time_s=maximum_force['sample_time_s'],
          inverted_contact_sample_count=len(inverted_records),
          inverted_negative_normal_sample_count=len(positive_inward),
          inverted_required_inward_peak_per_kg=maximum_inward['inward_force_requirement_per_kg'] if maximum_inward else (0 if inverted_records else None),
          inverted_required_inward_peak_time_s=maximum_inward['sample_time_s'] if maximum_inward else None,
          phase_statistics=phase_stats)
        for mass in MASSES:
            result.setdefault('inverted_mass_sensitivity',[]).append(dict(mass_kg=mass,
                required_inward_peak_N=mass*result['inverted_required_inward_peak_per_kg'] if inverted_records else None))
        uncut=[r for r in records if not r['derivative_support_crosses_source_edit']]
        result['source_edit_crossing_sample_count']=len(records)-len(uncut)
        if uncut:
            uncut_max=max(uncut,key=lambda r:r['acceleration_norm_m_s2'])
            result['peak_acceleration_excluding_source_edits_m_s2']=uncut_max['acceleration_norm_m_s2']
            result['peak_acceleration_excluding_source_edits_time_s']=uncut_max['sample_time_s']
        results.append(result)
    csv_write(data/'physics_mass_sensitivity.csv',mass_rows)
    largest_corner=max(corners,key=lambda r:r['delta_v_norm_m_s']) if corners else None
    ratio=results[1]['peak_acceleration_m_s2']/results[0]['peak_acceleration_m_s2'] if results[0]['peak_acceleration_m_s2'] else None
    summary=dict(schema_version=1,created_utc=datetime.now(timezone.utc).isoformat(),
      input_file=str(source),input_sha256=hashlib.sha256(snapshot).hexdigest(),
      input_rows=len(raw),input_time_range_s=[times[0],times[-1]],
      input_units='position cm converted to m; time seconds; angles degrees',
      gravity_world_m_s2=list(G),mass_hypotheses_kg=list(MASSES),mass_source='exploratory assumptions, not Tesla specifications',
      derivative_method='central second position difference; central first position difference; piecewise linear resampling; endpoints omitted; no smoothing',
      resultant_equation='F_non_gravity / mass = acceleration_world - gravity_world',
      normal_equation='q = dot(F_non_gravity / mass, outward_surface_to_car_normal); required inward contribution per kg = max(0,-q)',
      normal_assumptions='only explicitly listed contact hypothesis phases with zero roll; normal from interpolated pitch/yaw; partial release is uncertain; no measured collision normal, friction, pressure area, torque, load transfer or suspension solve; missing eligible samples means unknown, not zero force',
      normal_eligible_phase_labels=sorted(CONTACT_PHASES),
      source_edit_transition_intervals_s=cut_intervals,
      source_edit_warning='derivatives crossing edited shots have no validated continuous-time meaning; raw values retained and flagged; uncut derivatives still only quantify the authoring interpolant',
      approximation_limit='position follows authoring pivot, not independently measured center of mass; translational force is a point-mass proxy; COM offset and angular acceleration are unsolved',
      linear_interpolant_nonzero_velocity_jump_count=len(corners),largest_velocity_jump=largest_corner,
      pointwise_acceleration_convergence='NOT CONVERGENT at nonzero velocity-jump knots of the linear interpolant' if corners else 'no nonzero velocity jumps detected within 1e-6 m/s tolerance',
      peak_acceleration_ratio_48hz_over_24hz=ratio,
      sensitivity_warning='two grid spacings are a sensitivity check, not convergence proof; peak values depend on knot alignment and scale approximately as velocity jump / dt near corners; no finite physical peak may be inferred',
      results=results,physics_validation_passed=False,
      validation_status='NOT a verified Chaos physics mode; no real forces, controls, constraints or tire contacts were solved',
      forces_applied_to_engine=False)
    (data/'physics_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    largest_note=(f"最大插值速度跳变为 {largest_corner['delta_v_norm_m_s']:.3f} m/s，位于源采样时间 {largest_corner['source_time_s']:.6f} s。" if largest_corner else '没有超过阈值的插值速度跳变。')
    lines=['# 运动学逆动力学诊断','',
      '**结果不是已验证的车辆物理模式。** 本脚本只读取当前运动假设，计算维持该运动所需的合力必要条件；没有向 Unreal 施加隐藏力，也没有运行或通过 Chaos 验证。','',
      f"输入：`{source}`；SHA256：`{summary['input_sha256']}`；{len(raw)} 行。重跑命令：`python Scripts/physics_diagnostic.py --trajectory \"{source}\"`。轨迹更新后必须重新运行，以下数值仅对应该哈希。",'',
      '世界重力固定为 (0, 0, −9.80665) m/s²。位置由厘米换算为米。公式为 F非重力/m = a世界 − g世界；这个合力可由接触、附着、推力、气动力等共同承担，诊断不分配实际执行器。车辆1500/2000/2500 kg仅用于探索性敏感性，均非官方质量。','',
      '轨迹记录的是制作坐标轴心，尚未校准为质心，因此这里只是把它作为点质量代理。没有求解惯量、角加速度力矩、质心偏置、轮胎载荷转移、悬架、摩擦极限或储气/喷口能力。','',
      '| 差分步长 | 最大加速度 m/s² | 时间 s | 最大非重力合力/质量 N/kg | 倒挂所需向内分力峰值 N/kg |',
      '|---|---:|---:|---:|---:|']
    for r in results:
        inward=r['inverted_required_inward_peak_per_kg']
        inward_text=f'{inward:.3f}' if inward is not None else 'unknown（无适用样本）'
        lines.append(f"| 1/{round(1/r['step_s'])} s | {r['peak_acceleration_m_s2']:.3f} | {r['peak_acceleration_time_s']:.6f} | {r['peak_nongravity_force_per_kg']:.3f} | {inward_text} |")
    lines += ['',f"同一输入的48Hz/24Hz加速度峰值比为 {ratio:.3f}。{largest_note}",
      f"分段线性插值含 {len(corners)} 个非零速度跳变节点（阈值1e-6 m/s）。**在这些节点处，加速度没有有限的逐点收敛值**，理想表示是冲量；缩小差分步长只会改变/放大采样尖峰。两档步长不能证明物理加速度收敛，粗拟合尖点峰值不能当作实际车辆加速度或推力。脚本没有平滑掉尖点。",'',
      '原片分镜表给出的切镜过渡区间：'+str(cut_intervals)+'。差分支持范围跨越这些区间的样本已单独标记，保留原始数值而不把它解释成连续物理运动。各步长排除切镜后的峰值见JSON；即使不跨切镜，仍属于制作插值的运动学诊断。','',
      '仅在 ramp_contact_hypothesis 或 contact_or_partial_release_estimate 且滚转为零时，以俯仰/偏航推导“从道面指向车辆”的单位法向；partial release标签不证明仍然接触。q=(a−g)·n<0表示所需法向合力朝向道面；被动路面只能向外推，故必须由附着或其他向内外力提供至少−q N/kg。该数值不是测得吸力，不证明某装置已能提供；车身姿态与真实接触法向不一致时本估计失效。没有适用样本时输出unknown而不是0。','',
      '| 步长 | 探索质量 kg | 倒挂向内分力峰值 N |','|---|---:|---:|']
    for r in results:
        for m in r['inverted_mass_sensitivity']:
            value=m['required_inward_peak_N']
            value_text=f'{value:.1f}' if value is not None else 'unknown'
            lines.append(f"| {r['label']} | {m['mass_kg']} | {value_text} |")
    lines += ['',
      '飞行段若一段直线以恒速下落，a=0，则本公式必然要求向上9.80665 N/kg的非重力合力。这正说明该曲线是受控运动假设，而非自动满足重力的弹道；不能因此宣称发动机、储气或物理控制已验证。','',
      '输出：`Data/physics_timeseries_24hz.csv`、`physics_timeseries_48hz.csv` 记录世界加速度及逐分量非重力合力/质量；`physics_mass_sensitivity.csv` 记录各阶段质量敏感性；`physics_linear_corners.csv` 保留原始折点速度变化；`physics_summary.json` 保存输入哈希、公式和限制。边界样本不外推，跨阶段差分另有标记。']
    (validation/'physics_diagnostic.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(input_sha256=summary['input_sha256'],results=results,
        linear_corner_count=len(corners),physics_validation_passed=False),ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
