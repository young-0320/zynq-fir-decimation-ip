from sw import fir_decimator_demo as demo
from sw import fir_decimator_fft_viewer as viewer


def test_demo_delegates_main_to_fft_viewer():
    assert demo.main is viewer.main


def test_demo_reexports_live_demo_api():
    assert demo.N_IN == viewer.N_IN
    assert demo.N_OUT == viewer.N_OUT
    assert demo.FS_HZ == viewer.FS_HZ
    assert demo.run_scenario0 is viewer.run_scenario0
    assert demo.run_scenario1 is viewer.run_scenario1
    assert demo.run_interactive is viewer.run_interactive
