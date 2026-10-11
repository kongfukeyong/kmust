"""Structural and trust-boundary tests for real equation loss risks."""
import importlib.util,pathlib,tempfile,unittest,zipfile,xml.etree.ElementTree as ET
spec=importlib.util.spec_from_file_location('math_markup',pathlib.Path(__file__).with_name('math_markup.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def run(text):return '<m:r><m:t>'+text+'</m:t></m:r>'
def formula(body):return '<m:oMath xmlns:m="'+m.M+'">'+body+'</m:oMath>'
def convert(body):return m.omml_to_mathml(formula(body))
def tags(result):return [m.local(e.tag) for e in ET.fromstring(result['mathml']).iter()]

class FormulaTests(unittest.TestCase):
 def test_fraction_preserves_nested_numerator(self):
  x=convert('<m:f><m:num>'+run('a+b')+'</m:num><m:den>'+run('c+d')+'</m:den></m:f>')
  self.assertEqual(tags(x).count('mfrac'),1);self.assertTrue(x['complete']);self.assertIn('<mo>+</mo>',x['mathml'])
 def test_linear_fraction_does_not_flatten_into_ambiguous_division(self):
  x=convert('<m:f><m:fPr><m:type m:val="lin"/></m:fPr><m:num>'+run('a+b')+'</m:num><m:den>'+run('c+d')+'</m:den></m:f>');self.assertIn('mfrac',tags(x))
 def test_zero_bar_fraction(self):
  x=convert('<m:f><m:fPr><m:type m:val="noBar"/></m:fPr><m:num>'+run('n')+'</m:num><m:den>'+run('k')+'</m:den></m:f>');self.assertIn('linethickness="0"',x['mathml'])
 def test_sub_sup(self):
  x=convert('<m:sSubSup><m:e>'+run('x')+'</m:e><m:sub>'+run('i')+'</m:sub><m:sup>'+run('2')+'</m:sup></m:sSubSup>');self.assertIn('msubsup',tags(x))
 def test_prescripts(self):
  x=convert('<m:sPre><m:e>'+run('C')+'</m:e><m:sub>'+run('6')+'</m:sub><m:sup>'+run('14')+'</m:sup></m:sPre>');self.assertIn('mprescripts',tags(x))
 def test_square_and_nth_root(self):
  x=convert('<m:rad><m:radPr><m:degHide/></m:radPr><m:deg>'+run('3')+'</m:deg><m:e>'+run('x')+'</m:e></m:rad>');self.assertIn('msqrt',tags(x));self.assertNotIn('mroot',tags(x))
  x=convert('<m:rad><m:deg>'+run('3')+'</m:deg><m:e>'+run('x')+'</m:e></m:rad>');self.assertIn('mroot',tags(x))
 def test_integral_limits_and_integrand(self):
  x=convert('<m:nary><m:naryPr><m:chr m:val="∫"/><m:limLoc m:val="subSup"/></m:naryPr><m:sub>'+run('0')+'</m:sub><m:sup>'+run('1')+'</m:sup><m:e>'+run('f(x)dx')+'</m:e></m:nary>')
  self.assertIn('msubsup',tags(x));self.assertIn('∫',x['mathml']);self.assertIn('dx',x['mathml'])
 def test_display_nary_defaults_and_hidden_limits(self):
  xml=formula('<m:nary><m:naryPr><m:chr m:val="∑"/><m:supHide/></m:naryPr><m:sub>'+run('i=0')+'</m:sub><m:sup>'+run('n')+'</m:sup><m:e>'+run('x')+'</m:e></m:nary>')
  x=m.omml_to_mathml(xml,display=True);self.assertIn('munder',tags(x));self.assertNotIn('munderover',tags(x))
  x=m.omml_to_mathml(xml,display=True,defaults={'naryLim':'subSup'});self.assertIn('msub',tags(x))
 def test_matrix_shape(self):
  body='<m:m>'+''.join('<m:mr>'+''.join('<m:e>'+run(str(i+j))+'</m:e>' for j in range(3))+'</m:mr>' for i in range(2))+'</m:m>'
  x=convert(body);self.assertEqual(tags(x).count('mtr'),2);self.assertEqual(tags(x).count('mtd'),6)
 def test_delimiter_keeps_every_argument(self):
  x=convert('<m:d><m:dPr><m:begChr m:val="{"/><m:endChr m:val=""/></m:dPr><m:e>'+run('x')+'</m:e><m:e>'+run('y')+'</m:e><m:e>'+run('z')+'</m:e></m:d>')
  self.assertEqual(x['mathml'].count('>|</mo>'),2);self.assertIn('>z</mi>',x['mathml'])
 def test_function_accent_and_limit(self):
  x=convert('<m:func><m:fName><m:limLow><m:e>'+run('lim')+'</m:e><m:lim>'+run('x→0')+'</m:lim></m:limLow></m:fName><m:e><m:acc><m:accPr><m:chr m:val="→"/></m:accPr><m:e>'+run('v')+'</m:e></m:acc></m:e></m:func>')
  self.assertIn('munder',tags(x));self.assertIn('mover',tags(x));self.assertIn('\u2061',x['mathml'])
 def test_missing_argument_visible_not_silently_flattened(self):
  x=convert('<m:f><m:num>'+run('x')+'</m:num></m:f>');self.assertFalse(x['complete']);self.assertIn('merror',tags(x))
 def test_unknown_element_visible(self):
  x=convert('<m:futureThing>'+run('x')+'</m:futureThing>');self.assertFalse(x['complete']);self.assertIn('unsupported-omml-element',[w['code'] for w in x['warnings']])
 def test_untrusted_markup_escaped(self):
  x=convert(run('&lt;img src=x onerror=alert(1)&gt; &amp;'));self.assertNotIn('<img',x['mathml']);self.assertTrue(set(tags(x))<=m.ALLOWED_TAGS)
  for e in ET.fromstring(x['mathml']).iter():self.assertTrue(set(e.attrib)<=m.ALLOWED_ATTRS)
 def test_dtd_rejected(self):
  with self.assertRaises(ValueError):m.omml_to_mathml('<!DOCTYPE x [<!ENTITY y "oops">]>'+formula(run('x')))
 def test_relationship_resolution(self):
  self.assertEqual(m.resolve_target('word/document.xml','media/image1.png'),'word/media/image1.png')
  self.assertIsNone(m.resolve_target('word/document.xml','../../outside'))
  self.assertIsNone(m.resolve_target('word/document.xml','https://example.com/a'))
  self.assertIsNone(m.resolve_target('word/document.xml','%2E%2E/%2E%2E/a'))

class PackageTests(unittest.TestCase):
 def make_docx(self,path,body,rels=''):
  with zipfile.ZipFile(path,'w') as z:
   z.writestr('word/document.xml','<w:document xmlns:w="'+m.W+'" xmlns:m="'+m.M+'" xmlns:a="'+m.A+'" xmlns:r="'+m.R+'" xmlns:v="'+m.V+'" xmlns:o="'+m.O+'" xmlns:mc="'+m.MC+'"><w:body>'+body+'</w:body></w:document>')
   z.writestr('word/_rels/document.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+rels+'</Relationships>')
   z.writestr('word/media/formula.png',b'fake-test-preview');z.writestr('word/embeddings/equation.bin',b'not-executed')
 def test_mixed_paragraph_preserves_order_and_formula(self):
  with tempfile.TemporaryDirectory() as d:
   path=pathlib.Path(d)/'test.docx';self.make_docx(path,'<w:p><w:r><w:t>求 </w:t></w:r>'+formula('<m:f><m:num>'+run('a')+'</m:num><m:den>'+run('b')+'</m:den></m:f>')+'<w:r><w:t> 的值</w:t></w:r></w:p>')
   x=m.parse_docx(path);self.assertEqual([s['type'] for s in x['paragraphs'][0]['segments']],['text','math','text']);self.assertEqual(x['stats']['math'],1)
 def test_object_preview_relationship_and_external_no_fetch(self):
  rels='<Relationship Id="rImg" Target="media/formula.png" Type="image"/><Relationship Id="rOle" Target="embeddings/equation.bin" Type="oleObject"/><Relationship Id="rExternal" Target="https://example.invalid/x.png" TargetMode="External" Type="image"/>'
  body='<w:p><w:r><w:object><v:shape><v:imagedata r:id="rImg"/></v:shape><o:OLEObject r:id="rOle"/></w:object></w:r><w:r><w:drawing><a:blip r:link="rExternal"/></w:drawing></w:r></w:p>'
  with tempfile.TemporaryDirectory() as d:
   path=pathlib.Path(d)/'test.docx';self.make_docx(path,body,rels);x=m.parse_docx(path);segments=x['paragraphs'][0]['segments']
   self.assertEqual(segments[0]['embeddedObjectIds'],['rOle']);self.assertFalse(segments[1]['available']);self.assertEqual(x['paragraphs'][0]['matchText'],'[pic][pic]');self.assertEqual(len(x['media']),3)
 def test_alternate_content_fallback_not_duplicate(self):
  body='<w:p><mc:AlternateContent><mc:Choice Requires="unknown"><unknown/></mc:Choice><mc:Fallback><w:r><w:pict><v:imagedata r:id="rImg"/></w:pict></w:r></mc:Fallback></mc:AlternateContent></w:p>'
  with tempfile.TemporaryDirectory() as d:
   path=pathlib.Path(d)/'test.docx';self.make_docx(path,body,'<Relationship Id="rImg" Target="media/formula.png" Type="image"/>');x=m.parse_docx(path);self.assertEqual(x['stats']['images'],1)

if __name__=='__main__':unittest.main()
