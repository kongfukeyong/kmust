import copy,importlib.util,pathlib,unittest
from enrich_docx_math import RichIndex,normalized
from math_markup import omml_to_mathml,M

def math(body):return omml_to_mathml('<m:oMath xmlns:m="'+M+'">'+body+'</m:oMath>')
def run(text):return '<m:r><m:t>'+text+'</m:t></m:r>'
def document(*paragraphs):return {'paragraphs':[{'index':i+1,'segments':segments} for i,segments in enumerate(paragraphs)]}
def text(value):return {'type':'text','text':value}

class IndexTests(unittest.TestCase):
 def test_omml_full_span_preserved(self):
  formula=math('<m:f><m:num>'+run('a')+'</m:num><m:den>'+run('b')+'</m:den></m:f>')
  idx=RichIndex(document([text('1. 求 '),formula,text(' 的值。')]))
  rich,error=idx.select(idx.locate('求 ab 的值。'));self.assertIsNone(error);self.assertEqual([s['type'] for s in rich],['text','math','text']);self.assertIn('mfrac',rich[1]['mathml'])
 def test_partial_formula_is_rejected(self):
  idx=RichIndex(document([math('<m:f><m:num>'+run('a')+'</m:num><m:den>'+run('b')+'</m:den></m:f>')]))
  self.assertEqual(idx.select(idx.locate('a'))[1],'partial-formula-match')
 def test_duplicate_text_not_arbitrarily_selected(self):
  idx=RichIndex(document([text('相同题干。相同题干。')]))
  self.assertIsNone(idx.locate('相同题干。'))
 def test_labels_disambiguate_sqrt_two_from_plain_two(self):
  root=math('<m:rad><m:radPr><m:degHide/></m:radPr><m:deg/><m:e>'+run('2')+'</m:e></m:rad>')
  idx=RichIndex(document([text('A.1/2倍 C.'),root,text('倍 D.2倍')]))
  self.assertIsNone(idx.locate('2倍'))
  c=idx.locate_option('2倍','C',0,len(idx.text));d=idx.locate_option('2倍','D',0,len(idx.text))
  self.assertIn('msqrt',idx.select(c)[0][0]['mathml']);self.assertEqual(idx.select(d)[1],'plain-text-only')
 def test_paragraph_break_not_lost(self):
  root=math(run('x'));idx=RichIndex(document([text('求'),root],[text('的值')]))
  rich,error=idx.select(idx.locate('求x的值'));self.assertIsNone(error);self.assertTrue(any(s.get('text')=='\n' for s in rich))
 def test_inline_image_kept_without_guessing(self):
  idx=RichIndex(document([text('如图'),{'type':'image','mediaId':'r1'},text('求值')]))
  rich,error=idx.select(idx.locate('如图求值'));self.assertEqual(rich[1]['type'],'image')
 def test_trailing_image_same_paragraph_only(self):
  idx=RichIndex(document([text('如图求值'),{'type':'image','mediaId':'r1'}],[{'type':'image','mediaId':'r2'}]))
  rich,error=idx.select(idx.locate('如图求值'));self.assertEqual([s.get('mediaId') for s in rich if s['type']=='image'],['r1'])
 def test_unsupported_object_prevents_partial_replacement(self):
  idx=RichIndex(document([text('前'),{'type':'unsupported','kind':'embedded-object'},text('后')]))
  self.assertEqual(idx.select(idx.locate('前后'))[1],'unsupported-source-object')
 def test_normalization_is_only_width_whitespace_entities(self):
  self.assertEqual(normalized('（ x ＋ y ）&lt; ２'),'(x+y)<2');self.assertNotEqual(normalized('x+y'),normalized('x-y'))

if __name__=='__main__':unittest.main()
