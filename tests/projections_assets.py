import importlib.util,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('projection_assets',ROOT/'tools/projections/assets.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ProjectionAssetTests(unittest.TestCase):
 def test_catalog_sources_are_official_and_match_player_identity(self):
  for p in json.loads((ROOT/'projections_cache.json').read_text())['players']:self.assertTrue(m.source(p).startswith('https://assets.nhle.com/mugs/nhl/'))
  for player in [{'id':'../photo'},{'id':8478402,'headshot':'http://assets.nhle.com/mugs/nhl/latest/8478402.png'},{'id':8478402,'headshot':'https://other.example/mugs/nhl/latest/8478402.png'},{'id':8478402,'headshot':'https://assets.nhle.com/mugs/nhl/latest/8471675.png'}]:
   with self.assertRaises(ValueError):m.source(player)
 def test_publish_preserves_alpha_and_reuses_cached_portraits(self):
  raw=io.BytesIO();Image.new('RGBA',(336,336),(255,0,0,120)).save(raw,'PNG')
  with tempfile.TemporaryDirectory() as temporary:
   base=Path(temporary);data={'players':[{'id':8478402}]}
   with patch.object(m.urllib.request,'urlopen',side_effect=lambda *_args,**_kwargs:io.BytesIO(raw.getvalue())) as request:
    self.assertEqual(m.publish(data,base/'site',base/'cache'),1)
    self.assertEqual(m.publish(data,base/'site',base/'cache'),1);self.assertEqual(request.call_count,1)
   with Image.open(base/'site/8478402.webp') as image:self.assertEqual(image.size,(256,256));self.assertEqual(image.mode,'RGBA')
 def test_unavailable_portrait_does_not_publish_a_broken_file(self):
  with tempfile.TemporaryDirectory() as temporary:
   base=Path(temporary)
   with patch.object(m.urllib.request,'urlopen',side_effect=OSError('unavailable')):self.assertEqual(m.publish({'players':[{'id':8478402}]},base/'site',base/'cache'),0)
   self.assertEqual(list((base/'site').iterdir()),[])

if __name__=='__main__':unittest.main()
