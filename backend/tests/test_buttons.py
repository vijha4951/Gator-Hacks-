import json
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.routers.hardware import get_arduino
from app.services.arduino import ArduinoLED, HardwareError
from simulation.button_demo import output_state, build_button_circuit


@pytest.mark.parametrize('on,off,initial,expected', [
    (True,False,'off','on'),(False,True,'on','off'),(True,True,'on','off'),
    (False,False,'on','on'),(False,False,'off','off')])
def test_button_latching(on,off,initial,expected):
    assert output_state(on,off,initial)==expected


def test_button_wiring_and_active_low_inputs():
    c,code,_=build_button_circuit(on_pressed=True,off_pressed=False)
    nodes={n['id']:n for n in c['nodes']}
    assert nodes['button_on']['data']['isOpen'] is False
    assert nodes['button_off']['data']['isOpen'] is True
    assert any(e['source']=='controller' and e['sourceHandle']=='D5' and e['target']=='r1' for e in c['edges'])
    assert "digitalRead('D8')" in code and "digitalRead('D9')" in code


def test_hardware_state_and_virtual_button_routes():
    state={'state':'on','button_on_pressed':False,'button_off_pressed':False,'led_pin':5,'on_pin':9,'off_pin':8}
    connection=Mock()
    connection.readline.side_effect=[('STATE '+json.dumps(state)+'\n').encode(),b'LED_OFF\n']
    device=ArduinoLED('TEST',serial_factory=lambda *a,**k:connection,boot_delay=0)
    app.dependency_overrides[get_arduino]=lambda:device
    try:
        with TestClient(app) as client:
            r=client.get('/api/hardware/state')
            assert r.status_code==200 and r.json()['state']=='on'
            r=client.post('/api/hardware/buttons',json={'button':'off'})
            assert r.status_code==200 and r.json()['reply']=='LED_OFF'
        assert connection.write.call_args_list[0].args==(b'STATE\n',)
        assert connection.write.call_args_list[1].args==(b'LED_OFF\n',)
    finally:
        app.dependency_overrides.clear();device.close()


def test_old_sketch_cannot_report_button_state():
    connection=Mock();connection.readline.return_value=b'ERROR: Unknown command\n'
    device=ArduinoLED('TEST',serial_factory=lambda *a,**k:connection,boot_delay=0)
    with pytest.raises(HardwareError):device.read_state()
    assert connection.close.called


def test_intentionally_off_simulation_does_not_suggest_resistor(monkeypatch):
    from app.routers import buttons
    async def run(*args):
        return {'led_state':'off','led_current_mA':0,'simulated_with':'physbox'}
    monkeypatch.setattr(buttons,'run_button_demo',run)
    with TestClient(app) as client:
        r=client.post('/api/analyze/buttons',json={'on_pressed':False})
        assert r.status_code==200
        assert r.json()['analysis'] is None
        assert 'intentionally off' in r.json()['recommendation']
        assert client.post('/api/analyze/buttons',json={'voltage':8}).status_code==422


def test_button_correction_keeps_inputs(monkeypatch):
    from app.routers import buttons
    calls=[]
    async def run(*args):
        calls.append(args)
        return {'led_state':'on','led_current_mA':28 if args[0]==100 else 13,'simulated_with':'physbox'}
    monkeypatch.setattr(buttons,'run_button_demo',run)
    with TestClient(app) as client:
        r=client.post('/api/analyze/buttons',json={'resistance':100,'on_pressed':True})
        assert r.status_code==200
        assert r.json()['analysis']['corrected']['status']=='safe'
        assert len(calls)==2
        assert all(c[2:]==(True,False,'off') for c in calls)
