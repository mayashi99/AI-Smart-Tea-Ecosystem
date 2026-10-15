"""Step42 proof: Step26 feature equivalence and ALL 16 block input updates.

Does NOT run trained models or persist anything. Run real-model CLI afterwards.
"""
import argparse
from pathlib import Path
import numpy as np
from dynamic_spread_service import (ROOT,origin_from_snapshot,prepare_24h_inputs,
                                    arrays_for_disease,DISEASES,BLOCKS,validate_observation)


def run(root):
    origin=origin_from_snapshot(root)
    baseline=prepare_24h_inputs(root,origin,[],baseline_check=True)
    print('='*78)
    print('STEP42 - DYNAMIC ANY-BLOCK INPUT CONTRACT VALIDATION')
    print('='*78)
    print('Step26 saved/rebuilt max absolute feature difference:',baseline['baseline_max_abs_delta'])
    print('Past-only history rows:',len(baseline['window']),'| 14 days x 16 blocks x 4 diseases')
    for disease in DISEASES:
        hist,tab=arrays_for_disease(baseline,disease)
        assert hist.shape==(14,16,48) and tab.shape==(16,48)
    # One batch includes a distinct inspection for EACH of the 16 possible blocks.
    updates=[validate_observation(block,'Red Rust',100,i+1) for i,block in enumerate(BLOCKS)]
    changed=prepare_24h_inputs(root,origin,updates)
    base=baseline['window']; other=changed['window']
    for i,block in enumerate(BLOCKS):
        now=other.query('Disease_Name == "Red Rust" and Block_ID == @block').iloc[-1]
        assert abs(float(now['Sample_Incidence_Pct'])-(i+1))<1e-6
        assert float(now['Observation_Available'])==1
        assert float(now['Days_Since_Last_Inspection'])==0
    history,tabular=arrays_for_disease(changed,'Red Rust')
    assert history.shape==(14,16,48) and tabular.shape==(16,48)
    assert not np.allclose(tabular,arrays_for_disease(baseline,'Red Rust')[1])
    for disease in [d for d in DISEASES if d!='Red Rust']:
        assert np.allclose(arrays_for_disease(changed,disease)[1],
                           arrays_for_disease(baseline,disease)[1],rtol=1e-4,atol=1e-3)
    # Disease 2 and final-block selection are supported independently.
    grey=prepare_24h_inputs(root,origin,[validate_observation('B16','Grey Leaf',80,20)])
    leaf=grey['window'].query('Disease_Name == "Grey Leaf" and Block_ID == "B16"').iloc[-1]
    assert abs(float(leaf['Sample_Incidence_Pct'])-25)<1e-6
    for arguments in [('B17','Red Rust',100,20),('B01','Red Rust',15,20)]:
        try:validate_observation(*arguments)
        except ValueError:pass
        else:raise AssertionError('Invalid user observation accepted')
    print('PASS: all 16 blocks updated; other diseases unaffected; 14x16x48 sequences valid')
    print('PASS: bad IDs/counts rejected; no targets/models/retraining/runtime files used')
    print('NEXT: Step42 CLI runs actual saved models; not tested by THIS verification script')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=ROOT)
    run(p.parse_args().root)
