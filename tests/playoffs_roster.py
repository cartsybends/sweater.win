"""Current membership, reserve exceptions, same-day moves and source outages."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import copy,json,sys,tempfile,unittest,urllib.parse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/playoffs'))
from roster_eligibility import Membership
from advanced import availability,INJURY_URL
from data import TEAMS

NOW='2026-11-16T22:00:00Z'
PID=8482074


def roster(extra=()):
    return {'forwards':[{'id':100+i,'firstName':{'default':'Roster'},'lastName':{'default':str(i)}} for i in range(14)]+list(extra),
      'defensemen':[],'goalies':[{'id':900,'firstName':{'default':'Roster'},'lastName':{'default':'Goalie'}}]}


class CurrentMembership(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name);self.active=False;self.fail=False;self.club='CGY';self.minor=False;self.reserve=False;self.calls=[]

    def tearDown(self):self.tmp.cleanup()

    def fetch(self,url):
        self.calls.append(url)
        if self.fail:raise OSError('source unavailable')
        if '/v1/roster/' in url:return roster([{'id':PID,'firstName':{'default':'Connor'},'lastName':{'default':'Zary'}}] if self.active else [])
        if '/search/player?' in url:return [{'playerId':str(PID),'name':'Connor Zary'}]
        if '/player/' in url:return {'playerId':PID,'firstName':{'default':'Connor'},'lastName':{'default':'Zary'},'currentTeamAbbrev':self.club,
          'seasonTotals':[{'season':20262027,'leagueAbbrev':'NHL','gamesPlayed':2}]+([{'season':20262027,'leagueAbbrev':'AHL','gamesPlayed':6}] if self.minor else [])}
        if '/teams/' in url:return {'team':{'abbreviation':'CGY'},'athletes':[{'items':[{'displayName':'Roster '+str(i),'status':{'type':'active'},'injuries':[]} for i in range(15)]+
          ([{'displayName':'Connor Zary','status':{'type':'active'},'injuries':[{'status':'Injured Reserve'}]}] if self.reserve else [])}]}
        raise ValueError(url)

    def membership(self,now=NOW):
        m=Membership(self.folder,self.fetch,now);m.collect();return m

    def check(self,m,status='Out',**extra):
        return m.check(('CGY',{'name':'Connor Zary','player_id':PID,'status':status,**extra}))[1]

    def test_parent_affiliation_does_not_make_an_assigned_player_current(self):
        self.minor=True;m=self.membership();self.assertIsNone(self.check(m))
        self.assertIsNone(self.check(m,'Injured Reserve'))

    def test_rostered_player_survives_even_with_earlier_ahl_games(self):
        self.active=True;self.minor=True;r=self.check(self.membership());self.assertEqual(r['player_id'],PID);self.assertEqual(r['membership'],'NHL roster')

    def test_reserve_player_missing_active_roster_keeps_verified_identity(self):
        r=self.check(self.membership(),'Injured Reserve');self.assertEqual(r['player_id'],PID);self.assertEqual(r['membership'],'verified reserve')

    def test_official_search_and_profile_name_variants_keep_same_verified_id(self):
        fetch=self.fetch
        def variant(url):
            raw=fetch(url)
            if '/search/player?' in url:raw=[{'playerId':str(PID),'name':'C. Zary'}]
            return raw
        m=Membership(self.folder,variant,NOW);m.collect();self.assertEqual(self.check(m,'Injured Reserve')['player_id'],PID)

    def test_nickname_search_can_resolve_by_surname_without_choosing_another_player(self):
        fetch=self.fetch
        def nickname(url):
            if '/search/player?' in url:
                query=urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['q'][0]
                return [{'playerId':str(PID),'name':'Connor Zary'}] if query=='Zary' else [{'playerId':'1','name':'Connor McDavid'}]
            return fetch(url)
        m=Membership(self.folder,nickname,NOW);m.collect();self.assertEqual(self.check(m,'Injured Reserve')['player_id'],PID)

    def test_conditioning_assignment_requires_current_reserve_confirmation(self):
        self.minor=True;self.reserve=True;r=self.check(self.membership(),'Injured Reserve');self.assertEqual(r['player_id'],PID)

    def test_parent_club_without_current_nhl_appearances_needs_reserve_confirmation(self):
        fetch=self.fetch
        def no_games(url):
            raw=fetch(url)
            if '/player/' in url:raw['seasonTotals']=[]
            return raw
        m=Membership(self.folder,no_games,NOW);m.collect();self.assertIsNone(self.check(m,'Injured Reserve'))

    def test_current_other_team_overrules_stale_old_team_injury(self):
        self.club='TOR';self.reserve=True;self.assertIsNone(self.check(self.membership(),'Injured Reserve'))

    def test_same_day_assignment_refreshes_roster_after_fifteen_minutes(self):
        self.active=True;self.assertIsNotNone(self.check(self.membership()));self.active=False
        self.assertIsNone(self.check(self.membership('2026-11-16T22:16:00Z')))

    def test_roster_cache_is_dated_and_expires_instead_of_fabricating_membership(self):
        self.active=True;self.membership();self.fail=True
        m=self.membership('2026-11-16T22:16:00Z');self.assertEqual(m.status['CGY'],'cached');self.assertIsNotNone(self.check(m))
        m=self.membership('2026-11-17T22:01:00Z');self.assertEqual(m.status['CGY'],'unavailable');self.assertEqual(m.rosters['CGY'],[])

    def test_cached_injuries_are_reconciled_after_a_same_day_assignment(self):
        from unittest.mock import patch
        self.active=True;injury={'name':'Connor Zary','player_id':PID,'status':'Out'}
        folder=self.folder/'advanced';folder.mkdir();(folder/'injuries.json').write_text(json.dumps({'reported_at':NOW,'injuries':{t:[injury] if t=='CGY' else [] for t in TEAMS}}))
        def fetch(url):
            if url==INJURY_URL:raise OSError('injury outage')
            return self.fetch(url)
        with patch('advanced.CACHE',self.folder):
            first=availability([],fetch,NOW);self.assertEqual(first['injuries']['CGY'][0]['player_id'],PID)
            self.active=False;next=availability([],fetch,'2026-11-16T22:16:00Z');self.assertEqual(next['status'],'cached');self.assertEqual(next['injuries']['CGY'],[])


if __name__=='__main__':unittest.main()
