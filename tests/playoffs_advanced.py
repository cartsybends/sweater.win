"""Market provenance, chronological feature safety and shared v2 model behavior."""
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
import copy
import csv
import io
import json
import sys
import tempfile
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/playoffs'))
import advanced as A
import engine_v2 as E
import market as K
import starters as S
import evaluation as V
from games import validate_context
from data import TEAMS,records
from strength_v2 import State,Goalies,config,STARTER_PARAMETERS

NOW='2026-11-13T20:00:00Z'
GAME={'id':2026020310,'season':20262027,'date':'2026-11-13','start':'2026-11-14T02:00:00Z','home':'VAN','away':'NYR','neutral':False,'state':'FUT'}


def market_event():
    return {'id':'401892706','date':'2026-11-14T02:00:00Z','competitions':[{'competitors':[{'homeAway':'home','team':{'abbreviation':'VAN'}},{'homeAway':'away','team':{'abbreviation':'NYR'}}],
      'odds':[{'provider':{'name':'Draft Kings','priority':1},'moneyline':{'home':{'close':{'odds':'+185'},'open':{'odds':'+150'}},'away':{'close':{'odds':'-225'},'open':{'odds':'-180'}}}}]}]}


def fixture():
    rows=[];goalies=[];rosters={t:[{'id':100+i,'name':t+' Goalie','position':'goalies'}] for i,t in enumerate(TEAMS)}
    rosters['NYR']=[{'id':1000,'name':'Dylan Garand','position':'goalies'},{'id':1001,'name':'Joonas Korpisalo','position':'goalies'}]
    rosters['VAN']=[{'id':1002,'name':'Leevi Meriläinen','position':'goalies'},{'id':1003,'name':'Kevin Lankinen','position':'goalies'}]
    for season in [2023,2024,2025]:
        for i,t in enumerate(TEAMS):
            rows.append({'g':season*1000000+20001+i,'s':season,'d':f'{season}-11-01','t':t,'o':'SEA' if t!='SEA' else 'VAN','v':[3,3,3,3,2,2,2800,.6,350,.6,350]})
    finished={'id':2026020001,'season':20262027,'date':'2026-11-01','start':'2026-11-02T02:00:00Z','home':'VAN','away':'NYR','neutral':False,'state':'OFF','hg':2,'ag':4,'end':'REG'}
    for t,gf,ga in [('VAN',2,4),('NYR',4,2)]:
        rows.append({'g':finished['id'],'s':2026,'d':finished['date'],'t':t,'o':'NYR' if t=='VAN' else 'VAN','v':[gf,ga,3,3,2,2,2800,.6,350,.6,350]})
    for t in ['VAN','NYR']:
        for j,p in enumerate(rosters[t]):
            goalies.append({'g':2026020001+j,'s':2026,'d':f'2026-11-0{1+j}','t':t,'p':p['id'],'n':p['name'],'m':3600,'x':3.0,'a':2+j,'st':1,'w':int(j==0),'q':30})
    inputs={'version':2,'start':2026,'revision':'2026-11-13T06:00:00-05:00','source':A.TEAM_URL,'sha256':'a'*64,'teams':rows,'goalies':goalies,'births':{str(r['p']):'1998-01-01' for r in goalies}}
    games=[finished,copy.deepcopy(GAME)];rec=records(games)
    data={'start':2026,'season':20262027,'season_games':84,'games':games,'teams':[{'abbr':t,**rec[t]} for t in TEAMS]}
    availability={'rosters':rosters,'injuries':{t:[] for t in TEAMS},'status':'reported','reported_at':NOW,'observed_at':NOW}
    return data,inputs,availability


class Markets(unittest.TestCase):
    def test_exact_book_prices_not_symmetric_model_prices(self):
        m=K.event_market(market_event(),GAME,NOW)
        self.assertEqual((m['away'],m['home']),(-225,185));self.assertEqual(m['provider'],'DraftKings');self.assertTrue(K.valid_market(m,GAME,datetime.fromisoformat(NOW.replace('Z','+00:00'))))

    def test_mismatched_game_and_postgame_observations_rejected(self):
        e=market_event();e['competitions'][0]['competitors'][0]['team']['abbreviation']='SEA';self.assertIsNone(K.event_market(e,GAME,NOW))
        self.assertIsNone(K.event_market(market_event(),GAME,'2026-11-14T03:00:00Z'))
        e=market_event();e['date']='2026-11-15T02:00:00Z';self.assertIsNone(K.event_market(e,GAME,NOW))

    def test_bad_prices_never_become_market_quotes(self):
        for value in ['-1.5',None,'NaN',0,99,float('inf'),100001]:
            self.assertIsNone(K.american(value))
        self.assertEqual(K.american('EVEN'),100)
        e=market_event();del e['competitions'][0]['odds'][0]['moneyline'];self.assertIsNone(K.event_market(e,GAME,NOW))

    def test_outage_preserves_dated_quote_and_never_fabricates_price(self):
        prior={**GAME,'market':K.event_market(market_event(),GAME,NOW)}
        result=K.enrich_markets({'games':[copy.deepcopy(GAME)]},{'games':[prior]},lambda u:(_ for _ in ()).throw(OSError()),NOW)
        self.assertEqual(result['games'][0]['market'],prior['market'])
        result=K.enrich_markets({'games':[copy.deepcopy(GAME)]},{},lambda u:{'events':[]},NOW)
        self.assertNotIn('market',result['games'][0])

    def test_quote_fetched_after_start_is_not_backdated_to_refresh_start(self):
        result=K.enrich_markets({'games':[copy.deepcopy(GAME)]},{},lambda u:{'events':[market_event()]},NOW,clock=lambda:datetime(2026,11,14,3,tzinfo=timezone.utc))
        self.assertNotIn('market',result['games'][0])


class StarterReports(unittest.TestCase):
    def setUp(self):
        _,_,self.availability=fixture();self.rosters=self.availability['rosters'];self.source={'handle':'vzmercogliano','name':'Vince Mercogliano','teams':['NYR']}

    def post(self,text):
        return {'id':'123456789','text':text,'created_at':'2026-11-13T18:00:00Z'}

    def test_clear_confirmation_has_source_and_timestamp(self):
        r=S.parse_post(self.post('Garand will start tonight.'),'vzmercogliano',self.source,[GAME],self.rosters)[0]
        self.assertEqual(r['status'],'confirmed');self.assertEqual(r['player_id'],1000);self.assertTrue(S.valid_report(r,GAME,self.rosters,NOW))

    def test_morning_skate_is_not_confirmation(self):
        for text in ['Garand is in the starter crease at morning skate.','Garand is likely to start tonight.','Garand is expected to start tonight.']:
            rows=S.parse_post(self.post(text),'vzmercogliano',self.source,[GAME],self.rosters)
            self.assertTrue(all(r['status']!='confirmed' for r in rows))

    def test_wrong_team_negation_and_retweet_do_not_confirm(self):
        self.assertEqual(S.parse_post(self.post("Garand will not start tonight."),'vzmercogliano',self.source,[GAME],self.rosters)[0]['status'],'not_starting')
        self.assertEqual(S.parse_post(self.post('Meriläinen will start tonight.'),'vzmercogliano',self.source,[GAME],self.rosters),[])
        p=self.post('Garand will start tonight.');p['referenced_tweets']=[{'type':'retweeted'}];self.assertEqual(S.parse_post(p,'vzmercogliano',self.source,[GAME],self.rosters),[])

    def test_tonights_report_cannot_confirm_tomorrow_and_generic_confirmation_is_not_a_start(self):
        tomorrow={**GAME,'id':GAME['id']+1,'date':'2026-11-14','start':'2026-11-14T21:00:00Z'}
        rows=S.parse_post(self.post('Garand will start tonight.'),'vzmercogliano',self.source,[GAME,tomorrow],self.rosters)
        self.assertEqual([r['game_id'] for r in rows],[GAME['id']])
        self.assertEqual(S.parse_post(self.post('Garand confirmed for the goalie autograph session.'),'vzmercogliano',self.source,[GAME],self.rosters),[])

    def test_retraction_and_replacement_are_kept_separate(self):
        rows=S.parse_post(self.post("Update: Garand won't start tonight; Korpisalo will start tonight instead."),'vzmercogliano',self.source,[GAME],self.rosters)
        self.assertEqual({r['player_id']:r['status'] for r in rows},{1000:'not_starting',1001:'confirmed'})

    def test_report_for_another_date_or_unknown_roster_is_rejected(self):
        r=S.parse_post(self.post('Garand will start tonight.'),'vzmercogliano',self.source,[GAME],self.rosters)[0]
        self.assertFalse(S.valid_report({**r,'game_id':0},GAME,self.rosters,NOW));self.assertFalse(S.valid_report(r,GAME,{},NOW));self.assertFalse(S.valid_report({**r,'reported_at':'2026-11-15T00:00:00Z'},GAME,self.rosters,NOW))

    def test_token_without_explicit_read_cap_never_calls_paid_api(self):
        with patch.dict('os.environ',{'X_BEARER_TOKEN':'test-token','X_MAX_POSTS_PER_DAY':'0'}),patch.object(S.urllib.request,'urlopen') as request:
            _,status=S.collect([GAME],self.rosters,{},NOW)
        request.assert_not_called();self.assertEqual(status['status'],'disabled_until_read_cap_set')

    def test_daily_read_cap_and_recent_poll_interval_are_respected(self):
        old={'starter_feed':{'usage_day':NOW[:10],'posts_read':10}}
        with patch.dict('os.environ',{'X_BEARER_TOKEN':'test-token','X_MAX_POSTS_PER_DAY':'10'}),patch.object(S.urllib.request,'urlopen') as request:
            _,status=S.collect([GAME],self.rosters,old,NOW)
        request.assert_not_called();self.assertEqual(status['status'],'daily_read_limit')
        old={'starter_feed':{'checked_at':'2026-11-13T19:59:00Z'}}
        with patch.dict('os.environ',{'X_BEARER_TOKEN':'test-token','X_MAX_POSTS_PER_DAY':'10'}),patch.object(S.urllib.request,'urlopen') as request:
            S.collect([GAME],self.rosters,old,NOW)
        request.assert_not_called()

    def test_large_query_is_split_without_dropping_sources(self):
        sources=[{'handle':'long_official_team_'+t,'teams':[t]} for t in TEAMS]
        batches=S.search_batches(sources,self.rosters)
        self.assertEqual(sum(len(s) for s,q in batches),32);self.assertTrue(all(len(q)<=512 for s,q in batches))


class AdvancedModel(unittest.TestCase):
    def test_shared_game_and_simulation_mean_rates_are_identical(self):
        data,inputs,availability=fixture();engine=E.Engine(data,[],inputs,availability,{},NOW)
        h,a=engine.index['VAN'],engine.index['NYR'];rh,ra=engine.rating_rows[h],engine.rating_rows[a]
        lh,la=engine.adjust(GAME,rh['attack']*ra['defense'],ra['attack']*rh['defense'])
        probability,gh,ga,_=engine.predict(GAME)
        self.assertAlmostEqual(float(lh),gh,places=10);self.assertAlmostEqual(float(la),ga,places=10);self.assertTrue(0<probability<1)

    def test_injured_goalies_removed_without_equal_penalty_for_all_skaters(self):
        data,inputs,availability=fixture();availability['injuries']['NYR']=[{'player_id':1000,'name':'Dylan Garand','status':'Out','position':'G','return_estimate':None}]
        engine=E.Engine(data,[],inputs,availability,{},NOW);goalie=engine.context(GAME)['away']['goalie']
        self.assertEqual([r['id'] for r in goalie['players']],[1001]);self.assertAlmostEqual(sum(p['probability'] for p in goalie['players']),100)

    def test_confirmed_goalie_overrides_mixture_only_for_that_game(self):
        data,inputs,availability=fixture();report={'status':'confirmed','player_id':1000,'game_id':GAME['id'],'team':'NYR'}
        engine=E.Engine(data,[],inputs,availability,{(GAME['id'],'NYR'):report},NOW)
        g=engine.context(GAME)['away']['goalie'];self.assertEqual(g['status'],'confirmed');self.assertEqual(g['players'][0]['probability'],100)
        other={**GAME,'id':GAME['id']+1,'date':'2026-11-15','start':'2026-11-16T02:00:00Z'}
        self.assertEqual(engine.context(other)['away']['goalie']['status'],'projected')

    def test_current_injuries_and_confirmation_do_not_leak_into_reconstructions(self):
        data,inputs,availability=fixture();game={**GAME,'id':2026020010,'date':'2026-11-05','start':'2026-11-06T02:00:00Z'}
        first=E.Engine(data,[],inputs,availability,{},NOW).predict(game)
        availability['injuries']['NYR']=[{'player_id':1000,'status':'Out','return_estimate':None}]
        second=E.Engine(data,[],inputs,availability,{(game['id'],'NYR'):{'status':'confirmed','player_id':1001,'game_id':game['id'],'team':'NYR'}},NOW).predict(game)
        self.assertEqual(first[:3],second[:3]);self.assertEqual(second[3]['away']['injuries'],[])

    def test_refresh_crossing_start_uses_separate_historical_context(self):
        data,inputs,availability=fixture();availability['injuries']['NYR']=[{'player_id':1000,'name':'Dylan Garand','status':'Out'}]
        engine=E.Engine(data,[],inputs,availability,{},NOW)
        self.assertEqual(engine.context(GAME)['away']['injury_status'],'reported')
        reconstructed=engine.predict(GAME,force_historical=True)
        self.assertEqual(reconstructed[3]['away']['injury_status'],'not_reconstructed');self.assertEqual(reconstructed[3]['away']['injuries'],[])

    def test_newer_confirmation_overrides_older_injury_but_newer_injury_creates_conflict(self):
        data,inputs,availability=fixture()
        injury={'player_id':1000,'name':'Dylan Garand','status':'Out','return_estimate':None,'reported_at':'2026-11-13T11:00:00-05:00'}
        availability['injuries']['NYR']=[injury]
        report={'status':'confirmed','player_id':1000,'game_id':GAME['id'],'team':'NYR','reported_at':'2026-11-13T18:00:00Z'}
        goalie=E.Engine(data,[],inputs,availability,{(GAME['id'],'NYR'):report},NOW).context(GAME)['away']['goalie']
        self.assertEqual(goalie['status'],'confirmed');self.assertEqual(goalie['players'][0]['id'],1000)
        injury['reported_at']='2026-11-13T14:00:00-05:00'
        goalie=E.Engine(data,[],inputs,availability,{(GAME['id'],'NYR'):report},NOW).context(GAME)['away']['goalie']
        self.assertEqual(goalie['status'],'projected');self.assertEqual(goalie['report']['status'],'conflicting');self.assertEqual(goalie['players'][0]['id'],1001)

    def test_public_context_rejects_false_confirmation_and_nonconserving_probabilities(self):
        data,inputs,availability=fixture();game={**GAME,'context':E.Engine(data,[],inputs,availability,{},NOW).context(GAME)}
        validate_context(game)
        bad=copy.deepcopy(game);bad['context']['home']['goalie']['status']='confirmed'
        with self.assertRaises(AssertionError):validate_context(bad)
        bad=copy.deepcopy(game);bad['context']['home']['goalie']['players'][0]['probability']=101
        with self.assertRaises(AssertionError):validate_context(bad)

    def test_future_results_cannot_change_past_features(self):
        data,inputs,availability=fixture();state=State(2026,inputs['teams'],30,15);before=state.features('NYR')[0].copy()
        late={'id':999,'date':'2027-01-01','state':'OFF','home':'VAN','away':'NYR','hg':20,'ag':0,'end':'REG'}
        data['games'].append(late);engine=E.Engine(data,[],inputs,availability,{},NOW)
        past=engine.make_state('2026-11-01');np.testing.assert_array_equal(before,past.features('NYR')[0])

    def test_historical_weight_decays_after_new_games(self):
        data,inputs,_=fixture();state=State(2026,inputs['teams'],30,15);i=state.index['NYR'];old_weight=state.weights[i,0]
        game=data['games'][0]
        for n in range(20):state.update({**game,'id':9000+n})
        remaining_prior=old_weight*2**(-20/15);self.assertLess(remaining_prior/state.weights[i,0],.5)

    def test_missing_xg_never_becomes_fabricated_zero_shot_quality(self):
        data,inputs,_=fixture();state=State(2026,inputs['teams'],15,30);before=state.sums[state.index['NYR'],2]/state.weights[state.index['NYR'],2]
        state.update({**data['games'][0],'id':999});after=state.sums[state.index['NYR'],2]/state.weights[state.index['NYR'],2]
        self.assertAlmostEqual(before,after)

    def test_published_coefficients_are_finite_and_evaluation_is_recorded(self):
        p=config();self.assertEqual(len(p['features']),14);self.assertTrue(np.isfinite(p['coefficients']).all());self.assertTrue((np.array(p['scale'])>0).all())
        self.assertEqual(p['validation']['evaluation_season'],2025);self.assertLess(p['validation']['new']['brier'],p['validation']['baseline']['brier'])
        starter=json.loads(STARTER_PARAMETERS.read_text());self.assertEqual(starter['retrospective_evaluation']['season'],2025)


class AvailabilityAndEvaluation(unittest.TestCase):
    def test_source_outage_keeps_dated_injury_snapshot_and_marks_its_age(self):
        def failed(url):raise OSError('Source unavailable')
        with tempfile.TemporaryDirectory() as folder,patch.object(A,'CACHE',Path(folder)):
            directory=Path(folder)/'advanced';directory.mkdir()
            injuries={t:[] for t in TEAMS};injuries['NYR']=[{'player_id':1000,'name':'Dylan Garand','status':'Out'}]
            (directory/'injuries.json').write_text(json.dumps({'reported_at':NOW,'injuries':injuries}))
            recent=A.availability([],failed,'2026-11-13T21:00:00Z');self.assertEqual(recent['status'],'cached');self.assertEqual(recent['injuries'],injuries)
            older=A.availability([],failed,'2026-11-15T21:00:00Z');self.assertEqual(older['status'],'stale');self.assertEqual(older['injuries'],injuries)

    def test_forward_evaluation_excludes_reconstruction_and_freezes_actual_pregame(self):
        p={'home_win':40,'away_win':60,'basis':'pregame','at':NOW,'model':'test-v2'}
        output={'model':'test-v2','games':[{**GAME,'prediction':p}]}
        archive=V.update({},output,[]);self.assertEqual(len(archive['games']),1)
        output['games'][0]['prediction']={**p,'home_win':95,'basis':'reconstructed','at':None}
        archive=V.update(archive,output,[{**GAME,'state':'OFF','hg':2,'ag':3}])
        self.assertEqual(archive['games'][0]['prediction']['home_win'],40);self.assertAlmostEqual(V.scores(archive)['test-v2']['brier'],.16)
        self.assertEqual(V.update({},output,[])['games'],[])
        output['games'][0]['prediction']={**p,'at':GAME['start']}
        self.assertEqual(V.update({},output,[])['games'],[])


if __name__=='__main__':unittest.main()
