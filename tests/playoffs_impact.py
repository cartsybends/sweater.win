"""Player-impact data joins, replacement budgets, time safety and integration."""
from datetime import date,timedelta
from pathlib import Path
import copy
import base64
import json
import sys
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/playoffs'))
from impact_model import Team,Impact,KEYS,ROLES,waterfill,return_window,PARAMETERS
from impact_data import join
from engine_v2 import Engine
from strength_v2 import expected
from playoffs_advanced import fixture,GAME,NOW
import evaluation


def synthetic(injured=True,absent_history=False):
    model={'version':'test-impact','rates':{'ev':2.3,'pp':5.7,'pk':.7},'role_minutes':[48,6,6],'players':{},
      'replacement':{},'usage_history':{},'modeled_regulation_goal_share':.86,'goal_scale':.7,'trained_through':'2026-06-30','limitations':[],'inputs':{'sources':[]}}
    for pos in ('F','D'):model['replacement'][pos]={**dict.fromkeys(KEYS,0.),'usage_prior':[12,1,1]}
    data,inputs,availability=fixture();rows=[]
    for t in ('VAN','NYR'):
        for i in range(20):
            pid=10000+(0 if t=='VAN' else 100)+i;pos='F' if i<13 else 'D';usage=[18 if i==0 else 12,3 if i==0 else 1,1]
            p={'id':pid,'name':t+str(i),'position':'forwards' if pos=='F' else 'defensemen'}
            availability['rosters'][t].append(p)
            model['players'][str(pid)]={**dict.fromkeys(KEYS,0.),'training_minutes':{'ev':1000,'pp':300,'pk':100},'usage_prior':usage,'position':pos}
            if i==0:model['players'][str(pid)].update(off_ev=.15,off_pp=.10,def_ev=-.08)
            for j in range(10):
                if i==0 and absent_history and j:continue
                rows.append({'p':pid,'name':p['name'],'pos':pos,'g':2026020001+j,'date':f'2026-11-{j+1:02d}','team':t,
                  'seconds':sum(usage)*60,'ev':usage[0]*60,'pp':usage[1]*60,'pk':usage[2]*60})
    if injured:availability['injuries']['VAN']=[{'player_id':10000,'name':'VAN0','status':'Out','return_estimate':'2026-11-27'}]
    impact=Impact(data,inputs,availability,rows,NOW,model)
    return impact,data,inputs,availability


class Runtime(unittest.TestCase):
    def test_capped_minutes_conserve_exposure(self):
        result=waterfill([80,3,2,1],10,4)
        self.assertAlmostEqual(result.sum(),10);self.assertTrue(np.all(result<=4))
        impact,*_=synthetic();team=impact.teams['VAN']
        for assignments in team.assignments:
            minutes=np.array(list(assignments.values()));np.testing.assert_allclose(minutes.sum(axis=0),team.role_minutes*np.array([5,5,4]))
            for pid,values in assignments.items():
                self.assertLessEqual(values[1],6);self.assertLessEqual(values[2],6)

    def test_absence_changes_attack_and_defense_relative_to_replacements(self):
        impact,*_=synthetic();h,a=impact.multipliers('VAN','NYR','2026-11-13')
        self.assertLess(h,1);self.assertGreater(a,1)
        self.assertLess(impact.summary('VAN','2026-11-13')['players'][0]['attack_change_pct'],0)

    def test_healthy_teams_leave_baseline_exactly_unchanged(self):
        impact,*_=synthetic(False);h,a=impact.multipliers('VAN','NYR','2026-11-13')
        np.testing.assert_allclose([h,a],[1,1],atol=1e-14)

    def test_already_absent_player_is_not_deducted_twice(self):
        full,*_=synthetic();embedded,*_=synthetic(absent_history=True)
        a=full.multipliers('VAN','NYR','2026-11-13')[0];b=embedded.multipliers('VAN','NYR','2026-11-13')[0]
        self.assertGreater(b,a);self.assertLessEqual(b,1)

    def test_returning_player_missing_entire_current_season_still_enters_embedded_absence(self):
        impact,data,inputs,availability=synthetic();model=copy.deepcopy(impact.model)
        model['usage_history']={'2025':{'VAN':{'games':[[2025020001,'2025-11-01']],
          'players':{'10000':{'mask':'0x1','ev':base64.b64encode(bytes([36])).decode()}}}}}
        rows=[r for r in impact.rows if r['p']!=10000]
        missing=Impact(data,inputs,availability,rows,NOW,model)
        self.assertLess(missing.teams['VAN'].embedded[0],1)

    def test_return_date_simulations_match_exact_mixture_and_remain_monotone(self):
        impact,*_=synthetic();team=impact.teams['VAN'];early=team.simulation('2026-11-24',30000);later=team.simulation('2026-11-29',30000)
        np.testing.assert_allclose(early.mean(axis=0),team.mean('2026-11-24'),atol=.003)
        self.assertTrue(np.all(later[:,0]>=early[:,0]));self.assertEqual(len(team.draws),1)
        low,high,_=return_window({'return_estimate':'2026-11-27'},'2026-11-13')
        self.assertEqual(team.out_probabilities(date.fromordinal(high).isoformat()),[0.])
        self.assertEqual(team.out_probabilities(date.fromordinal(low-1).isoformat()),[1.])

    def test_unknown_return_estimates_never_restore_current_out_player_today(self):
        for estimate in (None,'bad','2026-11-01'):
            low,high,_=return_window({'return_estimate':estimate},'2026-11-13')
            self.assertGreater(low,date(2026,11,13).toordinal());self.assertGreaterEqual(high,low)

    def test_scalar_simulation_and_series_use_consistent_adjustments(self):
        impact,data,inputs,availability=synthetic();engine=Engine(data,[],inputs,availability,{},NOW,impact)
        baseline=Engine(data,[],inputs,availability,{},NOW)
        probability,lh,la,context=engine.predict(GAME);b=baseline.predict(GAME)
        factors=impact.multipliers('VAN','NYR',GAME['date']);np.testing.assert_allclose([lh,la],np.array(b[1:3])*factors)
        direct=engine.adjust(GAME,engine.rating_rows[engine.index['VAN']]['attack']*engine.rating_rows[engine.index['NYR']]['defense'],engine.rating_rows[engine.index['NYR']]['attack']*engine.rating_rows[engine.index['VAN']]['defense'])
        np.testing.assert_allclose(direct,[lh,la],atol=1e-12)
        h,a=impact.series_multipliers(['VAN','NYR'],np.array([0,1]),np.array([1,0]),GAME['date'])
        np.testing.assert_allclose([h[0],a[0]],factors)
        self.assertLess(context['home']['skater_impact']['win_change_pp'],0)

    def test_current_injury_never_enters_reconstructed_pregame_forecast(self):
        impact,data,inputs,availability=synthetic();engine=Engine(data,[],inputs,availability,{},NOW,impact)
        baseline=Engine(data,[],inputs,availability,{},NOW)
        np.testing.assert_allclose(engine.predict(data['games'][0],True)[:3],baseline.predict(data['games'][0],True)[:3])
        self.assertEqual(engine.predict(data['games'][0],True)[3]['home']['skater_impact']['status'],'not_reconstructed')

    def test_forward_results_keep_impact_versions_separate(self):
        rows=[{'prediction':{'model':'sweater-xg-v2','home_win':60,**({'impact_model':'sweater-skater-impact-v1'} if i else {})},'result':{'home_win':1}} for i in range(2)]
        self.assertEqual(len(evaluation.scores({'games':rows})),2)
        rows[1]['prediction']['impact_baseline_home_win']=58
        scored=evaluation.scores({'games':rows})
        self.assertEqual(len(scored),3)
        self.assertAlmostEqual(scored['sweater-xg-v2+sweater-skater-impact-v1 (without skater adjustment)']['brier'],.42**2)


class JoinedSources(unittest.TestCase):
    def test_goal_clock_uses_ending_shift_and_ignores_empty_net(self):
        game={'id':2026020001,'season':20262027,'home':'VAN','away':'NYR','date':'2026-11-01'}
        players=[{'p':p,'team':'VAN' if p<=5 or p==11 else 'NYR'} for p in range(1,12)]
        goalies=[{'p':90,'t':'VAN'},{'p':91,'t':'NYR'}]
        shifts=[[game['id'],p,1,0,60 if p==1 else 120,1 if p<=5 or p==90 else 2] for p in range(1,11)]+[[game['id'],p,1,0,120,1 if p==90 else 2] for p in (90,91)]+[[game['id'],11,1,60,120,1]]
        shot={'t':60,'period':1,'home':True,'hc':5,'ac':5,'shooter':1,'goal':1,'hg':0,'ag':0,'q':.2,'empty':False,'home_team':'VAN','away_team':'NYR'}
        joined=join(game,shifts,players,goalies,[shot]);self.assertEqual(joined['stints'][0][5],[1,0]);self.assertEqual(joined['stints'][1][6],1)
        empty={**shot,'q':None,'empty':True};self.assertEqual(join(game,shifts,players,goalies,[empty])['finishing'],[])

    def test_published_release_has_separate_chronological_checks(self):
        model=json.loads(PARAMETERS.read_text());self.assertEqual(model['version'],'sweater-skater-impact-v1')
        self.assertGreater(len(model['players']),1000);self.assertGreater(sum(s['games'] for s in model['inputs']['sources'] if s['season']<2026),3800)
        check=model['game_validation'];self.assertEqual(check['calibration_season'],2025);self.assertEqual(check['evaluation_season'],2026)
        self.assertGreaterEqual(check['goal_scale'],0);self.assertLessEqual(check['goal_scale'],1.5)
        self.assertIn('dressed',check['scope']);self.assertEqual(check['baseline_2026']['games'],check['adjusted_2026']['games'])
        for p in model['players'].values():self.assertTrue(np.isfinite([p[k] for k in KEYS]).all())


if __name__=='__main__':unittest.main()
