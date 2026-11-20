import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
import monitor as m

CFG=json.loads(m.CFG.read_text())
NOW=datetime(2026,11,20,12,0,tzinfo=timezone.utc)
def article(title,body='',url='https://example.org/news/1'):
    return {'title':title,'body':body,'url':url,'publisher':'Example Publisher','author':'Not stated','date':'2026-11-20','published':NOW.isoformat(),'institutions':['ISRO']}

class TestMonitor(unittest.TestCase):
    def test_tone_separate_from_critical(self):
        a=m.local_analysis(article('ISRO launch delayed by weather','A routine postponement was announced.'))
        self.assertEqual(a['tone'],'Neutral'); self.assertFalse(m.qualifies(a,CFG))
        a=m.local_analysis(article('Gaganyaan delayed again: first flight unlikely before February'))
        self.assertEqual(a['tone'],'Neutral'); self.assertTrue(m.qualifies(a,CFG))
        a=m.local_analysis(article('PSLV mission failure reported','ISRO reported a mission failure.'))
        self.assertEqual(a['tone'],'Neutral'); self.assertEqual(a['impact'],'High'); self.assertTrue(m.qualifies(a,CFG))
    def test_negative_and_positive(self):
        a=m.local_analysis(article('ISRO faces criticism over mission planning','Experts criticised ISRO for poor governance.'))
        self.assertTrue(m.qualifies(a,CFG)); self.assertEqual(a['tone'],'Negative')
        a=m.local_analysis(article('ISRO successfully completes mission'))
        self.assertFalse(m.qualifies(a,CFG)); self.assertEqual(a['tone'],'Positive')
    def test_denial(self):
        a=m.local_analysis(article('ISRO says no failure of satellite mission'))
        self.assertFalse(a['critical'])
    def test_dedup(self):
        a=article('ISRO faces criticism',url='https://www.example.org/news/1?utm_source=x')
        b=article('ISRO faces criticism',url='http://example.org/news/1')
        self.assertEqual(m.identities(a),m.identities(b))
        self.assertFalse(set(m.identities(a))&set(m.identities(article(a['title'],url='https://other.org/news/1'))))
    def test_email(self):
        a=article('ISRO faces criticism <script>'); a.update(m.local_analysis(a))
        sub,plain,rich=m.format_email([a],NOW)
        self.assertIn(a['url'],plain); self.assertIn('Tone: Negative',plain); self.assertIn('Impact Analysis',rich); self.assertNotIn('<script>',rich)
    def test_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.json'; s={'version':1,'sent':{'key':1},'checked':{}}; m.save_state(s,p); self.assertEqual(s,m.load_state(p))
            p.write_text('{}'); self.assertRaises(ValueError,m.load_state,p)
    def test_publisher_verification(self):
        a=article('ISRO faces criticism over mission planning')
        obj={'@type':'NewsArticle','headline':a['title'],'datePublished':(NOW-timedelta(minutes=10)).isoformat(),'publisher':{'name':'Example Publisher'},'articleBody':'ISRO faces criticism over mission planning. Experts criticised ISRO for poor governance and raised questions about programme timelines. The report discusses the issues in detail and provides context on planning.'}
        html=('<html><head><script type="application/ld+json">'+json.dumps(obj)+'</script></head><body></body></html>').encode()
        with patch('monitor.get',return_value=(a['url'],html)):
            out,why=m.verify(a,NOW,CFG); self.assertEqual(why,'verified'); self.assertEqual(out['title'],a['title'])
            self.assertEqual(m.verify(a,NOW+timedelta(hours=8),CFG)[1],'outside window')
        obj.pop('datePublished'); html=('<script type="application/ld+json">'+json.dumps(obj)+'</script>').encode()
        with patch('monitor.get',return_value=(a['url'],html)):
            self.assertEqual(m.verify(a,NOW,CFG)[1],'exact original publication time unavailable')
    def test_failed_email_not_marked_sent(self):
        a=article('ISRO faces criticism over mission planning','Experts criticised ISRO for poor governance.')
        state={'version':1,'sent':{},'checked':{}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(m,'ROOT',Path(tmp)), patch.object(m,'load_state',return_value=state), patch.object(m,'mail_config'), patch.object(m,'discover',return_value=([a],{'test':1})), patch.object(m,'verify',return_value=(a,'verified')), patch.object(m,'send',side_effect=RuntimeError('SMTP failure')), patch.object(m,'save_state') as save:
            with self.assertRaises(RuntimeError): m.run()
            self.assertFalse(state['sent']); save.assert_not_called()
    def test_sent_persists_and_duplicate_skips(self):
        a=article('ISRO faces criticism over mission planning','Experts criticised ISRO for poor governance.')
        state={'version':1,'sent':{},'checked':{}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(m,'ROOT',Path(tmp)), patch.object(m,'load_state',return_value=state), patch.object(m,'mail_config'), patch.object(m,'discover',return_value=([a],{'test':1})), patch.object(m,'verify',return_value=(a,'verified')), patch.object(m,'send') as send, patch.object(m,'save_state') as save:
            m.run(); self.assertTrue(state['sent']); save.assert_called_once(); send.assert_called_once()
            state['checked']={}; m.run(); send.assert_called_once()

if __name__=='__main__': unittest.main()
