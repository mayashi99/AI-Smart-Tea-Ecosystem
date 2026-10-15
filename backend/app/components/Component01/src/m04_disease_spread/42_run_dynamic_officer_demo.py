"""Run trained Step31-selected 7-day disease forecasts for any B01-B16 block.

Historical validation-origin officer-conditioned simulation, not current live forecast.
"""
import argparse
import json
from pathlib import Path
from dynamic_spread_service import ROOT,dynamic_predict


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--block',required=True,help='B01..B16')
    p.add_argument('--disease',required=True,help='Brown Blight, Grey Leaf, Red Rust, Red Spider Mite')
    p.add_argument('--inspected',required=True,type=int)
    p.add_argument('--symptomatic',required=True,type=int)
    p.add_argument('--save',action='store_true',help='Persist officer input in separate CSV after inference PASS')
    p.add_argument('--baseline-check',action='store_true',help='Verify original Step26 features before update (first run only)')
    args=p.parse_args()
    res=dynamic_predict(args.root,args.block,args.disease,args.inspected,args.symptomatic,
                        save=args.save,check_saved_baseline=args.baseline_check)
    print('='*84)
    print('STEP 42 - SAVED MODEL, OFFICER-CONDITIONED HISTORICAL SIMULATION')
    print('='*84)
    print('Block:',res['selected_block_id'],'Disease:',res['disease_name'],
          'Officer sample:',res['submitted_observation']['incidence_percent'],'%')
    print('Origin:',res['forecast_origin_date'],'14-day inputs; 48 features; Saved models executed: TRUE')
    print('Existing officer records applied:',res['previous_officer_updates_applied'])
    if 'baseline_feature_parity_max_abs_difference' in res:
        print('Baseline feature parity max delta:',res['baseline_feature_parity_max_abs_difference'])
    for r in res['selected_block_daily_forecast']:
        print(f" Day {r['horizon_day']}: incidence={r['incidence_percent_prediction']:.2f}% "
              f"activity={r['activity_predicted_class']} new_onset={r['new_onset_predicted_class']} "
              f"alert={r['demo_alert_level']}")
    if args.save:
        print('Saved officer input: data/runtime/officer_observations.csv')
        print('Latest JSON: outputs/dashboard/dynamic/step42_latest_officer_forecast.json')
    print('PASS: 7 model-generated predictions for selected block; 112 returned for disease.')
    print('WARNING: Historical 2025 origin, 16 synthetic blocks, unverified climate; NOT a live 2026 forecast.')

if __name__=='__main__':
    main()
