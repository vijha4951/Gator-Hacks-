"""Behavioral MCU + SPICE simulation of active-low ON/OFF buttons.
Volt executes JavaScript controller logic, not the Uno's compiled AVR firmware.
"""
import asyncio
import json
from fastmcp import Client
from simulation.led_demo import build_led_circuit


def output_state(on_pressed, off_pressed, initial_state="off"):
    if off_pressed:
        return "off"
    if on_pressed:
        return "on"
    return initial_state


def build_button_circuit(resistance=220, led_forward_voltage=2.0,
                         on_pressed=False, off_pressed=False, initial_state="off"):
    c = build_led_circuit(5, resistance, led_forward_voltage)
    state = output_state(on_pressed, off_pressed, initial_state)
    code = ("pinMode('D5','OUTPUT'); pinMode('D9','INPUT'); pinMode('D8','INPUT');\n"
            f"let lit = {1 if initial_state == 'on' else 0};\n"
            "while(true) { if(digitalRead('D8') === 0) lit=0; "
            "else if(digitalRead('D9') === 0) lit=1; digitalWrite('D5',lit); sleep(10); }")
    c['nodes'].append({'id':'controller','type':'mcu','position':{'x':180,'y':380},
                       'data':{'label':'Two-button controller (D5/D8/D9)','code':code}})
    for node_id,pin,pressed,x in [('on','D9',on_pressed,50),('off','D8',off_pressed,400)]:
        c['nodes'] += [
            {'id':'pull_'+node_id,'type':'resistor','position':{'x':x,'y':400},'data':{'value':20000,'label':'20k'}},
            {'id':'button_'+node_id,'type':'switch','position':{'x':x,'y':500},'data':{'label':node_id.upper(),'isOpen':not pressed}}]
        for source,sh,target,th in [('sg1','pos','pull_'+node_id,'in'),('pull_'+node_id,'out','controller',pin),
                                    ('pull_'+node_id,'out','button_'+node_id,'in'),('button_'+node_id,'out','g1','in')]:
            c['edges'].append({'id':f'{source}-{target}-{th}','source':source,'sourceHandle':sh,'target':target,'targetHandle':th,'type':'smoothstep'})
    # Drive the LED from the MCU output, while the source supplies the MCU/pullups.
    for e in c['edges']:
        if e['source']=='sg1' and e['target'] in ('r1','led1'):
            e['source']='controller';e['sourceHandle']='D5'
    c['edges'] += [
        {'id':'mcu-vcc','source':'sg1','sourceHandle':'pos','target':'controller','targetHandle':'5V','type':'smoothstep'},
        {'id':'mcu-gnd','source':'controller','sourceHandle':'GND','target':'g1','targetHandle':'in','type':'smoothstep'}]
    return c, code, state


async def run_button_demo(resistance=220, led_forward_voltage=2.0,
                          on_pressed=False, off_pressed=False, initial_state="off"):
    c, code, state = build_button_circuit(resistance, led_forward_voltage, on_pressed, off_pressed, initial_state)
    async with Client('http://localhost:3141/mcp',timeout=60) as client:
        async def call(name,args=None):
            r=await client.call_tool(name,args or {})
            if r.is_error:raise RuntimeError(f'{name}: {r}')
            if r.data is not None:return r.data
            for content in r.content:
                if getattr(content,'text',None):return json.loads(content.text)
            raise RuntimeError(f'{name}: empty response')
        apps=await call('detect_apps')
        volt=next((a for a in apps if a['id']=='circuit'),{})
        if not volt.get('wsConnected') or volt.get('sessionCount') != 1:
            raise RuntimeError('Keep exactly one Volt tab connected')
        await call('circuit_set_circuit',{**c,'runSim':False})
        pins=[{'id':p,'type':t,'side':side} for p,t,side in [
            ('D5','digital','left'),('D8','digital','left'),('D9','digital','left'),('D3','digital','left'),
            ('GND','ground','right'),('5V','power','right'),('A1','analog','right'),('A0','analog','right')]]
        pins[5]['voltage']=5
        await call('circuit_define_mcu',{'nodeId':'controller','presetKey':'dip8_standard','pins':pins,'code':code})
        valid=await call('circuit_validate_circuit')
        if not valid.get('ok'):raise RuntimeError(f'Invalid two-button circuit: {valid}')
        result=await call('circuit_run_sim')
        if not result.get('ok'):raise RuntimeError('Two-button simulation failed')
        await asyncio.sleep(2)
        previous = None
        stable = 0
        for _ in range(40):
            wave=await call('circuit_get_waveforms');nodes={n['id']:n for n in wave.get('nodes',[])}
            samples=nodes.get('led1',{}).get('current_array',[])
            if samples and 'voltage' in nodes.get('vm_led',{}):
                current = samples[-1] * 1000
                voltage = nodes['vm_led']['voltage']
                # The MCU's first SPICE pass can still contain its initial LOW output.
                # Wait for a waveform consistent with the requested controller state.
                matches = (abs(current) < .1 and abs(voltage) < .1) if state == 'off' else voltage > .1
                value = (current, voltage)
                stable = stable + 1 if value == previous and matches else (1 if matches else 0)
                previous = value
                if stable < 3:
                    await asyncio.sleep(.25)
                    continue
                return {'led_state':state,'led_current_mA':samples[-1]*1000 if resistance else None,
                        'led_voltage_V':nodes['vm_led']['voltage'],'simulated_with':'physbox',
                        'controller_model':'Volt JavaScript behavior with SPICE; not AVR firmware emulation'}
            await asyncio.sleep(.25)
        raise RuntimeError('Two-button waveform did not match the controller state; try again with Volt visible')
