"""Read Linux power_supply units without guessing unknown battery values."""
# SPDX-License-Identifier: GPL-3.0-or-later
import math


def number(path, read):
    try:
        value=float(read(path) or 'nan')
        return value if math.isfinite(value) and value>=0 else None
    except (TypeError,ValueError): return None


def battery_details(path, read):
    get=lambda name:number(path/name,read)
    status=read(path/'status')
    energy,full,design=get('energy_now'),get('energy_full'),get('energy_full_design')
    charge,cfull,cdesign=get('charge_now'),get('charge_full'),get('charge_full_design')
    power,current,voltage=get('power_now'),get('current_now'),get('voltage_now')
    watts=power/1e6 if power is not None else current*voltage/1e12 if current is not None and voltage is not None else None
    health=full/design*100 if full is not None and design else cfull/cdesign*100 if cfull is not None and cdesign else None
    remaining=get('time_to_full_now' if status=='Charging' else 'time_to_empty_now')
    if not remaining:
        amount=(max(0,full-energy) if status=='Charging' else energy) if energy is not None and (status!='Charging' or full is not None) else None
        if amount is not None and watts and watts>0: remaining=amount/1e6/watts*3600
        else:
            amount=(max(0,cfull-charge) if status=='Charging' else charge) if charge is not None and (status!='Charging' or cfull is not None) else None
            remaining=amount/current*3600 if amount is not None and current and current>0 else None
    if status not in ('Charging','Discharging') or remaining is not None and (not math.isfinite(remaining) or remaining>7*86400): remaining=None
    return {'name':path.name,'status':status,'health':round(min(100,health),1) if health is not None else None,
            'powerW':round(watts,2) if watts is not None else None,'secondsRemaining':round(remaining) if remaining is not None else None}


def aggregate(devices):
    health=[d['health'] for d in devices if d['health'] is not None]
    return {'devices':devices,'health':round(sum(health)/len(health),1) if health else None,
            'powerW':round(sum(d['powerW'] for d in devices),2) if devices and all(d['powerW'] is not None for d in devices) else None,
            # shortcut: multi-pack ETA is omitted; add energy-weighted estimation if multi-battery hardware is targeted.
            'secondsRemaining':devices[0]['secondsRemaining'] if len(devices)==1 else None}
