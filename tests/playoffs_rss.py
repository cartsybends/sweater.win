"""News certainty, calendar binding, source provenance and conservative polling."""
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
import hashlib,importlib.util,json,sys,tempfile,unittest,xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/playoffs'))
import starter_rss as R
import starters as S
ROOT=Path(__file__).resolve().parents[1]
NOW='2026-11-13T23:50:00Z'
GAME={'id':2026020310,'date':'2026-11-13','start':'2026-11-14T02:00:00Z','home':'VAN','away':'NYR'}
ROSTERS={'NYR':[{'id':1000,'name':'Dylan Garand','position':'goalies'},{'id':1001,'name':'Joonas Korpisalo','position':'goalies'}],'VAN':[]}
def xml(headline='Confirmed starter Friday',text='Garand will start at Vancouver on Friday.',date='Fri, 13 Nov 2026 11:44:00 AM PST'):
 root=ET.Element('rss');channel=ET.SubElement(root,'channel');ET.SubElement(channel,'title').text='RotoWire.com Latest NHL News';ET.SubElement(channel,'ttl').text='10';item=ET.SubElement(channel,'item')
 for k,v in {'title':'Dylan Garand: '+headline,'description':text,'link':'https://www.rotowire.com//hockey/player/dylan-garand-1234','pubDate':date,'guid':'nhl123'}.items():ET.SubElement(item,k).text=v
 return ET.tostring(root)
class News(unittest.TestCase):
 def test_confirmed_facts_keep_link_id_and_published_time_without_prose(self):
  rows,interval=R.parse(xml(),[GAME],ROSTERS,NOW);self.assertTrue(rows);r=rows[0]
  self.assertEqual(r['status'],'confirmed');self.assertEqual(r['source_url'],'https://www.rotowire.com/hockey/player/dylan-garand-1234');self.assertEqual(r['reported_at'],'2026-11-13T19:44:00Z');self.assertEqual(interval,600);self.assertTrue(S.valid_report(r,GAME,ROSTERS,NOW));self.assertNotIn('text',r)
 def test_expectations_and_morning_skate_never_confirm(self):
  for headline,text in [('Expected to start','Garand is expected to start Friday.'),('First goalie off Friday','Garand was first goalie off during the morning skate Friday.'),('Expected to start','Garand will start Friday.')]:
   rows,_=R.parse(xml(headline,text),[GAME],ROSTERS,NOW);self.assertTrue(rows);self.assertTrue(all(r['status']=='likely' for r in rows))
 def test_wrong_opponent_date_unknown_player_and_poststart_reports_rejected(self):
  for payload in [xml(text='Garand will start against Edmonton on Friday.'),xml(text='Garand will start Friday.',date='Thu, 12 Nov 2026 11:44:00 AM PST').replace(b'Friday',b'Thursday'),xml().replace(b'Dylan Garand:',b'Unknown Goalie:'),xml(date='Fri, 13 Nov 2026 11:44:00 PM PST')]:
   self.assertEqual(R.parse(payload,[GAME],ROSTERS,NOW)[0],[])
 def test_noon_midnight_and_report_timezone_are_explicit(self):
  self.assertEqual(R.timestamp('Fri, 13 Nov 2026 12:00:00 AM PST'),'2026-11-13T08:00:00Z');self.assertEqual(R.timestamp('Fri, 13 Nov 2026 12:00:00 PM PST'),'2026-11-13T20:00:00Z')
  with self.assertRaises(ValueError):R.timestamp('Fri, 13 Nov 2026 12:00:00')
 def test_short_feed_rolloff_304_cache_and_outage_preserve_known_facts(self):
  calls=[]
  def fetch(headers):calls.append(headers);return 200,xml(),{'ETag':'"version-1"'}
  rows,meta=R.collect([GAME],ROSTERS,{},NOW,fetch);self.assertTrue(rows);old={'starter_feed':meta}
  kept,cached=R.collect([GAME],ROSTERS,old,'2026-11-13T23:55:00Z',lambda _:self.fail('Publisher TTL must be respected'));self.assertEqual(kept,rows)
  kept,meta=R.collect([GAME],ROSTERS,old,'2026-11-14T00:01:00Z',lambda headers:(304,b'',{}));self.assertEqual(kept,rows)
  root=ET.fromstring(xml());channel=root.find('channel');channel.remove(channel.find('item'))
  kept,meta=R.collect([GAME],ROSTERS,{'starter_feed':meta},'2026-11-14T00:12:00Z',lambda headers:(200,ET.tostring(root),{}));self.assertEqual(kept,rows)
  kept,meta=R.collect([GAME],ROSTERS,{'starter_feed':meta},'2026-11-14T00:23:00Z',lambda headers:(_ for _ in ()).throw(OSError()));self.assertEqual(kept,rows);self.assertEqual(meta['status'],'unavailable')
 def test_rescheduled_game_rejects_a_previous_start_confirmation(self):
  rows,_=R.parse(xml(),[GAME],ROSTERS,NOW);self.assertFalse(S.valid_report(rows[0],{**GAME,'start':'2026-11-15T02:00:00Z'},ROSTERS,NOW))
 def test_rss_mode_never_calls_x_even_with_token_and_read_cap(self):
  with patch.dict('os.environ',{'STARTER_REPORT_SOURCE':'rss','X_BEARER_TOKEN':'test-only','X_MAX_POSTS_PER_DAY':'100'}),patch.object(R,'collect',return_value=([],{'source':'RotoWire RSS','x_requests':0})),patch.object(S.urllib.request,'urlopen') as request:
   _,meta=S.collect([GAME],ROSTERS,{},NOW)
  request.assert_not_called();self.assertEqual(meta['x_requests'],0)
class Crests(unittest.TestCase):
 def test_derived_crest_artwork_stays_vector_and_preserves_official_paths(self):
  spec=importlib.util.spec_from_file_location('sweater_crest_builder',ROOT/'build_sweater.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
  with tempfile.TemporaryDirectory() as folder:
   out=Path(folder);builder.copy_community_logos(out);self.assertEqual(len(list((out/'team-crests').glob('*.svg'))),32)
   for path in (out/'team-crests').glob('*.svg'):
    original=ET.fromstring((out/'team-logos'/path.name).read_text());derived=ET.fromstring(path.read_text())
    self.assertNotEqual(original.get('viewBox'),derived.get('viewBox'));self.assertEqual([ET.tostring(p) for p in original],[ET.tostring(p) for p in derived]);self.assertFalse(any(e.tag.endswith('image') for e in derived.iter()))
if __name__=='__main__':unittest.main()
